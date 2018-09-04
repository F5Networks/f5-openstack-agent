# coding=utf-8
# Copyright (c) 2016-2018, F5 Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import base64

from cryptography.hazmat import backends
from cryptography.hazmat.primitives import serialization
from cryptography import x509
from f5_openstack_agent.lbaasv2.drivers.bigip import exceptions as f5_ex
from oslo_log import log as logging
from pyasn1.codec.der import decoder as der_decoder
from pyasn1.codec.der import encoder as der_encoder
from pyasn1_modules import rfc2315
import six


X509_BEG = b'-----BEGIN CERTIFICATE-----'
X509_END = b'-----END CERTIFICATE-----'
PKCS7_BEG = b'-----BEGIN PKCS7-----'
PKCS7_END = b'-----END PKCS7-----'

LOG = logging.getLogger(__name__)


def get_intermediates_pems(intermediates=None):
    """Split the input string into individual x509 text blocks

    :param intermediates: PEM or PKCS7 encoded intermediate certificates
    :returns: A list of strings where each string represents an
              X509 pem block surrounded by BEGIN CERTIFICATE,
              END CERTIFICATE block tags
    """
    if X509_BEG in intermediates:
        for x509Der in _split_x509s(intermediates):
            yield _prepare_x509_cert(_get_x509_from_pem_bytes(x509Der))
    else:
        for x509Der in _parse_pkcs7_bundle(intermediates):
            yield _prepare_x509_cert(_get_x509_from_der_bytes(x509Der))


def _prepare_x509_cert(cert=None):
    """Prepares a PEM-encoded X509 certificate for printing

    :param intermediates: X509Certificate object
    :returns: A PEM-encoded X509 certificate
    """
    return cert.public_bytes(encoding=serialization.Encoding.PEM).strip()


def _split_x509s(xstr):
    """Split the input string into individual x509 text blocks

    :param xstr: A large multi x509 certificate blcok
    :returns: A list of strings where each string represents an
    X509 pem block surrounded by BEGIN CERTIFICATE,
    END CERTIFICATE block tags
    """
    curr_pem_block = []
    inside_x509 = False
    if type(xstr) == six.binary_type:
        xstr = xstr.decode('utf-8')
    for line in xstr.replace("\r", "").split("\n"):
        if inside_x509:
            curr_pem_block.append(line)
            if line == X509_END.decode('utf-8'):
                yield six.b("\n".join(curr_pem_block))
                curr_pem_block = []
                inside_x509 = False
            continue
        else:
            if line == X509_BEG.decode('utf-8'):
                curr_pem_block.append(line)
                inside_x509 = True


def _parse_pkcs7_bundle(pkcs7):
    """Parse a PKCS7 certificate bundle in DER or PEM format

    :param pkcs7: A pkcs7 bundle in DER or PEM format
    :returns: A list of individual DER-encoded certificates
    """
    # Look for PEM encoding
    if PKCS7_BEG in pkcs7:
        try:
            for substrate in _read_pem_blocks(pkcs7):
                for cert in _get_certs_from_pkcs7_substrate(substrate):
                    yield cert
        except Exception:
            LOG.exception('Unreadable Certificate.')
            raise f5_ex.UnreadableCert

    # If no PEM encoding, assume this is DER encoded and try to decode
    else:
        for cert in _get_certs_from_pkcs7_substrate(pkcs7):
            yield cert


def _read_pem_blocks(data):
    """Parse a series of PEM-encoded blocks

    This method is based on pyasn1-modules.pem.readPemBlocksFromFile, but
    eliminates the need to operate on a file handle and is a generator.

    :param data: A long text string containing one or more PEM-encoded blocks
    :param markers: A tuple containing the test strings that indicate the
                    start and end of the PEM-encoded blocks
    :returns: An ASN1 substrate suitable for DER decoding.

    """
    stSpam, stHam, stDump = 0, 1, 2
    startMarkers = {PKCS7_BEG.decode('utf-8'): 0}
    stopMarkers = {PKCS7_END.decode('utf-8'): 0}
    idx = -1
    state = stSpam
    if type(data) == six.binary_type:
        data = data.decode('utf-8')
    for certLine in data.replace('\r', '').split('\n'):
        if not certLine:
            continue
        certLine = certLine.strip()
        if state == stSpam:
            if certLine in startMarkers:
                certLines = []
                idx = startMarkers[certLine]
                state = stHam
                continue
        if state == stHam:
            if certLine in stopMarkers and stopMarkers[certLine] == idx:
                state = stDump
            else:
                certLines.append(certLine)
        if state == stDump:
            yield b''.join([base64.b64decode(x) for x in certLines])
            state = stSpam


def _get_certs_from_pkcs7_substrate(substrate):
    """Extracts DER-encoded X509 certificates from a PKCS7 ASN1 DER substrate

    :param substrate: The substrate to be processed
    :returns: A list of DER-encoded X509 certificates
    """
    try:
        contentInfo, _ = der_decoder.decode(substrate,
                                            asn1Spec=rfc2315.ContentInfo())
        contentType = contentInfo.getComponentByName('contentType')
    except Exception:
        LOG.exception('Unreadable Certificate.')
        raise f5_ex.UnreadableCert
    if contentType != rfc2315.signedData:
        LOG.exception('Unreadable Certificate.')
        raise f5_ex.UnreadableCert

    try:
        content, _ = der_decoder.decode(
            contentInfo.getComponentByName('content'),
            asn1Spec=rfc2315.SignedData())
    except Exception:
        LOG.exception('Unreadable Certificate.')
        raise f5_ex.UnreadableCert

    for cert in content.getComponentByName('certificates'):
        yield der_encoder.encode(cert)


def _get_x509_from_pem_bytes(certificate_pem):
    """Parse X509 data from a PEM encoded certificate

    :param certificate_pem: Certificate in PEM format
    :returns: crypto high-level x509 data from the PEM string
    """
    if type(certificate_pem) == six.text_type:
        certificate_pem = certificate_pem.encode('utf-8')
    try:
        x509cert = x509.load_pem_x509_certificate(certificate_pem,
                                                  backends.default_backend())
    except Exception:
        LOG.exception('Unreadable Certificate.')
        raise f5_ex.UnreadableCert
    return x509cert


def _get_x509_from_der_bytes(certificate_der):
    """Parse X509 data from a DER encoded certificate

    :param certificate_der: Certificate in DER format
    :returns: crypto high-level x509 data from the DER-encoded certificate
    """
    try:
        x509cert = x509.load_der_x509_certificate(certificate_der,
                                                  backends.default_backend())
    except Exception:
        LOG.exception('Unreadable Certificate.')
        raise f5_ex.UnreadableCert
    return x509cert
