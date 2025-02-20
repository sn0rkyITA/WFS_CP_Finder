from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QMessageBox, QSizePolicy
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.core import QgsProject, QgsRectangle
from qgis.gui import QgsDockWidget
import os
import csv
import requests
import json
from io import BytesIO

class WFSCPFINDER:
    def __init__(self, iface):
        """Inizializza il plugin e le variabili principali."""
        self.iface = iface  # Interfaccia QGIS
        self.plugin_name = "My QGIS Plugin"  # Nome del plugin
        self.dock_widget = None  # Dock widget principale
        self.timer = None  # Timer per il conteggio
        self.province_comuni = self.load_province_comuni()  # Carica province e comuni da CSV
        self.token = None  # Token di sessione
        
    def load_captcha(self):
        """ Scarica e visualizza il CAPTCHA nella QLabel self.picture."""
        captcha_url = "https://geoportale.cartografia.agenziaentrate.gov.it/age-inspire/srv/ita/Captcha?type=image&lang=it"
        
        try:
            response = requests.get(captcha_url)
            if response.status_code == 200:
                self.cookie = response.cookies.get_dict()  # Memorizza i cookie per la sessione
                pixmap = QPixmap()
                pixmap.loadFromData(BytesIO(response.content).read())  # Carica l'immagine del CAPTCHA
                self.picture.setPixmap(pixmap.scaled(self.picture.size(), Qt.KeepAspectRatio))
            else:
                QMessageBox.critical(self.dock_widget, "Errore", f"Errore nel download del CAPTCHA: {response.status_code}")
        except Exception as e:
            QMessageBox.critical(self.dock_widget, "Errore", f"Errore durante il download del CAPTCHA: {str(e)}")    

    def send_captcha_response(self):
        """Invia la risposta del CAPTCHA per ottenere il token."""
        captcha_text = self.captcha_input.text().strip()
        if not captcha_text:
            QMessageBox.warning(self.dock_widget, "Errore", "Per favore, inserisci il testo del CAPTCHA.")
            return

        captcha_check_url = f"https://geoportale.cartografia.agenziaentrate.gov.it/age-inspire/srv/ita/Captcha?type=check&captcha={captcha_text}" # URL per la verifica del CAPTCHA
        
        headers = {"Cookie": f"JSESSIONID={self.cookie.get('JSESSIONID')}"}

        try:
            # Invia la risposta del CAPTCHA con il cookie
            response = requests.get(captcha_check_url, headers=headers)
            print(response.text)  # Mostra la risposta del server per il debug

            # Verifica la risposta del server
            if response.status_code == 200:
                jSonResp = response.json()
                if jSonResp.get("token"):
                    # Salva il token e avvia il timer
                    self.token = jSonResp["token"]
                    self.time_left = 600
                    self.timer.start(1000)  # Avvia il timer che conta i secondi
                    self.timer_label.setText(f"Contatore: {self.time_left}")
                else:
                    QMessageBox.warning(self.dock_widget, "Errore", "Captcha errato o token non trovato.")
                    self.time_left = 0
                    self.timer_label.setText(f"Contatore: {self.time_left}")
            else:
                QMessageBox.critical(self.dock_widget, "Errore", f"Errore nella verifica del CAPTCHA: {response.status_code}")
        
        except Exception as e:
            QMessageBox.critical(self.dock_widget, "Errore", f"Errore durante la verifica del CAPTCHA: {str(e)}")

    def update_counter(self):
        """Aggiorna il contatore ogni secondo."""
        if self.timer_counter > 0:
            self.timer_counter -= 1
            self.timer_label.setText(f"Contatore: {self.timer_counter}")
        else:
            self.timer.stop()
            QMessageBox.information(self.dock_widget, "Tempo Scaduto", "Il token è scaduto.")

    def load_province_comuni(self):
        """
        Funzione per caricare i dati dal file CSV.
        """
        path = os.path.dirname(__file__)
        csv_file = os.path.join(path, "ListaComuni.csv")
        
        province_comuni = {}
        try:
            with open(csv_file, newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    provincia = row["Nome_Provincia"]
                    comune = row["Nome_Comune"]
                    codice_provincia = row["Codice_Provincia"]
                    codice_comune = row["Codice_Comune"]
                    chiave_provincia = (provincia, codice_provincia)
                    if chiave_provincia not in province_comuni:
                        province_comuni[chiave_provincia] = []
                    province_comuni[chiave_provincia].append((comune, codice_comune))
                    
        except FileNotFoundError:
            print(f"File {csv_file} non trovato.")
        
        return province_comuni

    def initGui(self):
        """
        Funzione per inizializzare la GUI del plugin.
        """
        self.dock_widget = QgsDockWidget(self.plugin_name, self.iface.mainWindow())
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5) 

        # Labels e ComboBox per Province e Comuni
        self.label_provincia = QLabel("Provincia:")
        self.combo_provincia = QComboBox()
        for provincia, codice_provincia in self.province_comuni.keys():
            self.combo_provincia.addItem(provincia, codice_provincia)  # Aggiungi solo il nome e codice della provincia
        
        self.combo_provincia.currentIndexChanged.connect(self.update_comuni)
        
        self.label_comune = QLabel("Comune:")
        self.combo_comune = QComboBox()
        
        self.combo_provincia.setEditable(True)
        self.combo_comune.setEditable(True)
        
        self.combo_provincia.view().setFixedHeight(150)   
        self.combo_provincia.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.combo_provincia.setFixedWidth(170)        
        self.combo_comune.view().setFixedHeight(150)  
        self.combo_comune.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.combo_comune.setFixedWidth(170)        
        
        # Aggiungere gli altri campi (Foglio, Particella, ecc.) come prima
        self.labels = [QLabel(text) for text in ["Foglio:", "Particella:"]]
        self.textboxes = [QLineEdit() for _ in range(2)]
        for textbox in self.textboxes:
            textbox.setFixedWidth(170)

        
        # Layout per Province e Comuni
        row1 = QHBoxLayout()
        row1.addWidget(self.label_provincia)
        row1.addWidget(self.combo_provincia)

        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(self.label_comune)
        row2.addWidget(self.combo_comune)

        layout.addLayout(row2)
        
        
        
        
        for label, textbox in zip(self.labels, self.textboxes):
            row = QHBoxLayout()
            row.addWidget(label)
            row.addWidget(textbox)
            layout.addLayout(row)
        
        
        self.btn_execute = QPushButton("Avvia Sessione")
        self.btn_execute.clicked.connect(self.load_captcha)  # Collegamento al metodo load_captcha
        layout.addWidget(self.btn_execute)
        
        # PictureBox
        self.picture = QLabel()
        self.picture.setFixedSize(200, 100)
        self.picture.setStyleSheet("border: 1px solid black;")
        layout.addWidget(self.picture, alignment=Qt.AlignCenter)
        self.picture.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Captcha input
        self.captcha_input = QLineEdit()
        layout.addWidget(self.captcha_input)
        # Pulsanti
        self.btn_validate = QPushButton("Invia Risposta")
        self.btn_validate.clicked.connect(self.send_captcha_response)  # Collegamento al metodo per inviare il CAPTCHA
        
        self.btn_locate = QPushButton("Posiziona in Mappa")
        self.btn_locate.clicked.connect(self.locate_on_map)
        
        layout.addWidget(self.btn_validate)
        layout.addWidget(self.btn_locate)
        
        # Timer e Label Contatore
        self.timer_label = QLabel("Contatore: 0")
        layout.addWidget(self.timer_label)
        
        widget.setLayout(layout)
        self.dock_widget.setWidget(widget)
        
        
        # Aggiungi il DockWidget all'interfaccia QGIS
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)





        # Creazione del QTimer e associazione al widget
        self.timer = QTimer(widget)  # Il parent è ora il widget
        self.timer.timeout.connect(self.update_counter)
        self.counter = 0




    def unload(self):
        """
        Funzione per scaricare il plugin e rimuovere il DockWidget.
        """
        self.iface.removeDockWidget(self.dock_widget)
        self.dock_widget = None


    def ricercamappale(self, prov, cod_com, foglio, part, code):
        # Costruzione dell'URL
        url_address = f"https://wms.cartografia.agenziaentrate.gov.it/inspire/ajax/ajax.php?op=getGeomPart&prov={prov}&cod_com={cod_com}&foglio={foglio}&num_part={part}/&tkn={code}"
        print(url_address)
        # Effettua la richiesta GET
        try:
            response = requests.get(url_address)
            response.raise_for_status()  # Verifica che la richiesta sia stata completata con successo
        except requests.exceptions.RequestException as ex:
            print(f"Errore durante la richiesta: {ex}")
            return 0

        # Estrai la risposta JSON
        try:
            data = response.json()
            print("Risposta JSON ricevuta:", data)  # Stampa la risposta JSON per il debug
        except ValueError:
            print("Errore nel decodificare la risposta JSON.")
            return 0

        # Verifica se la risposta contiene errori
        if "ERRX" in data:
            print("Errore nella risposta del server")
            return 0

        # Estrai la geometria dalla risposta JSON
        try:
            # Supponiamo che la risposta JSON abbia una struttura come segue:
            # {"GEOMETRIA": ['{"type": "Polygon", "coordinates": [[...]]}']}
            geometria_stringa = data.get('GEOMETRIA', [])[0]
            geometria = json.loads(geometria_stringa)

            # Estrai le coordinate del poligono
            coordinates = geometria.get('coordinates', [])[0]
            if len(coordinates) < 3:  # Verifica che ci siano almeno 3 punti per formare un poligono
                print("Il mappale non esiste o non è un poligono valido")
                return 0

            # Estrai tutte le coordinate (per il calcolo del centroide, per esempio)
            est1, nord1 = coordinates[0]
            est2, nord2 = coordinates[1]
            est3, nord3 = coordinates[2]
            est4, nord4 = coordinates[3]

            # Calcola il centroide (media delle coordinate)
            est_avg = sum([est for est, _ in coordinates]) / len(coordinates)
            nord_avg = sum([nord for _, nord in coordinates]) / len(coordinates)

            # Restituisci i valori
            return {
                'nord': nord_avg,
                'est': est_avg,
                'bb_est1': est1,
                'bb_nord1': nord1,
                'bb_est2': est2,
                'bb_nord2': nord2,
                'bb_est3': est3,
                'bb_nord3': nord3,
                'bb_est4': est4,
                'bb_nord4': nord4
            }
        except KeyError:
            print("Errore nei dati JSON: struttura non corretta")
            return 0

 
    

    
    def locate_on_map(self):
        # Ottieni i valori dalle combobox e textbox
        provincia = self.combo_provincia.currentData()  # Ottieni il codice della provincia (non il nome)
        comune = self.combo_comune.currentData()  # Ottieni il codice del comune (non il nome)
        foglio = self.textboxes[0].text()  # Leggi il QLineEdit per il foglio
        particella = self.textboxes[1].text().zfill(5)  # Leggi il QLineEdit per la particella
        token = self.token  # Usa il token salvato nella variabile self.token

    # Chiamata alla funzione per ottenere le coordinate
        result = self.ricercamappale(provincia, comune, foglio, particella, token)
        print(result)
        if result:
            # Estrai i valori dalla risposta
            bb_est1 = result.get("bb_est1")
            bb_nord1 = result.get("bb_nord1")
            bb_est3 = result.get("bb_est3")
            bb_nord3 = result.get("bb_nord3")

            if None not in (bb_est1, bb_nord1, bb_est3, bb_nord3):
                # Crea il rettangolo dell'estensione
                extent = QgsRectangle(bb_est1, bb_nord1, bb_est3, bb_nord3)

                # Ottieni il canvas della mappa
                canvas = self.iface.mapCanvas()

                # Imposta l'estensione del canvas per centrare sulla zona
                canvas.setExtent(extent)

                # Aggiorna la mappa
                canvas.refresh()
            else:
                QMessageBox.warning(None, "Errore", "Coordinate della bounding box non valide.")
        else:
            QMessageBox.warning(None, "Errore", "Non è stato possibile posizionare il mappale.")

        
        
        
        
        
    
    def update_counter(self):
        self.counter += 1
        self.timer_label.setText(f"Contatore: {self.counter}")
    
    def update_comuni(self):
        # Azzera la lista dei comuni
        self.combo_comune.clear()
        # Recupera la provincia selezionata
        selected_index = self.combo_provincia.currentIndex()
        if selected_index == -1:
            return  # Nessuna selezione, esci dalla funzione
        selected_provincia = self.combo_provincia.currentText()
        selected_codice_provincia = self.combo_provincia.itemData(selected_index)  # Recupera il codice provincia associato
    
        chiave_provincia = (selected_provincia, selected_codice_provincia)
    
        # Aggiunge i comuni in base alla provincia selezionata
        if chiave_provincia in self.province_comuni:
            comuni = self.province_comuni[chiave_provincia]
            for comune, codice_comune in comuni:
                self.combo_comune.addItem(comune, codice_comune)  # Associa il codice al nome del comune
    
    def set_image(self, image_path):
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                raise Exception("Immagine non valida.")
            self.picture.setPixmap(pixmap.scaled(self.picture.size(), Qt.KeepAspectRatio))
        except Exception as e:
            QMessageBox.critical(self.dock_widget, "Errore", f"Impossibile caricare l'immagine: {str(e)}")


# Funzione classFactory per il plugin
def classFactory(iface):
    """
    Questa funzione deve restituire un'istanza del tuo plugin.
    """
    return WFSCPFINDER(iface)
