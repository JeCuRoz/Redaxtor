import logging
from logging.handlers import TimedRotatingFileHandler

# configuración común del logging para todos los módulos

# formato de los registro del log
LOG_FORMAT = '%(asctime)s %(levelname)s: %(message)s'

# nivel de regstro del log
# FIXME: el nivel de logging deberia especificarse en un archivo de configuracion
LOG_LEVEL = logging.INFO

# número de ficheros de logs a guardar
BACKUP_COUNT = 5

# unidad de tiempo para medir los intervalos en los que se rotarán los logs
INTERVAL_CATEGORY = 'D'  # dias

# intervalo para crear un archivo de log
INTERVAL = 1


# crea un log por consola
# si se proporciona un nombre de fichero también vuelca el log a ese fichero
def get_logger(log_file=None, log_level=LOG_LEVEL, log_format=LOG_FORMAT):

    # log básico por consola
    logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)
    logger = logging.getLogger()

    if log_file:
        # se creará un fichero de log y se volcarán los registros en él
        try:
            file_handler = TimedRotatingFileHandler(
                log_file, when=INTERVAL_CATEGORY, interval=INTERVAL, backupCount=BACKUP_COUNT
            )
            _format = logging.Formatter(log_format)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(_format)
            logger.addHandler(file_handler)
        except IOError:
            logger.error(f'Ha ocurrido un error con el fichero de log: {log_file}')
        except Exception as e:
            logger.error(f'Ha ocurrido un error inesperado: {e}')
            raise e

    return logger
