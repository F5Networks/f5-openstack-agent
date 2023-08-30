# coding=utf-8
import base64
import hashlib

from cryptography.fernet import Fernet


def generate_key(serial_number):
    h = hashlib.md5(serial_number.encode('utf-8')).hexdigest()
    return base64.urlsafe_b64encode(h)


def encrypt_data(serial_number, data):
    f = Fernet(generate_key(serial_number))
    return f.encrypt(data.encode())


def decrypt_data(serial_number, data):
    f = Fernet(generate_key(serial_number))
    return f.decrypt(data.encode())
