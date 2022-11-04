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


def en_de_test():
    key_194 = '564d7cf4-bef9-4e16-006889a2f037'
    username = 'admin'
    password = 'P@ssw0rd123'

    print("encrypt 194")
    u_e = encrypt_data(key_194, username)
    print(u_e)
    u_d = decrypt_data(key_194, u_e)
    print(u_d)

    p_e = encrypt_data(key_194, password)
    print(p_e)
    p_d = decrypt_data(key_194, p_e)
    print(p_d)

    print("encrypt 193")
    key_193 = '564d0f1c-eb2f-44df-dc424d351438'
    u_e = encrypt_data(key_193, username)
    print(u_e)
    u_d = decrypt_data(key_193, u_e)
    print(u_d)

    p_e = encrypt_data(key_193, password)
    print(p_e)
    p_d = decrypt_data(key_193, p_e)
    print(p_d)


if __name__ == '__main__':
    en_de_test()
