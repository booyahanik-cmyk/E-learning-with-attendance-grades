# Route Django's MySQL backend through PyMySQL (pure-Python driver, easy on Windows).
# PyMySQL reports a mysqlclient-compatible version, so this shim alone satisfies
# Django 6's driver-version check.
import pymysql

pymysql.install_as_MySQLdb()
