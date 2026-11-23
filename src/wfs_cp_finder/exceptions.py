"""Eccezioni specifiche della libreria WFS_CP_Finder."""


class CatastoError(Exception):
    """Errore generico nella comunicazione con i servizi catastali."""


class CaptchaError(CatastoError):
    """Il CAPTCHA non e' stato superato o la sessione non e' iniziata."""


class SessionExpiredError(CatastoError):
    """Il token di sessione e' scaduto: necessario un nuovo CAPTCHA."""


class ParcelNotFoundError(CatastoError):
    """La particella richiesta non esiste o non e' stata restituita."""
