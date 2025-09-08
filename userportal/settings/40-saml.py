# SAML2 settings
import saml2
import saml2.saml

# These variables are defined in 10-base.py
INSTALLED_APPS += ['djangosaml2']
MIDDLEWARE += ['djangosaml2.middleware.SamlSessionMiddleware']
AUTHENTICATION_BACKENDS += ['userportal.authentication.staffSaml2Backend']

SAML_SESSION_COOKIE_NAME = 'saml_session'
SESSION_COOKIE_SECURE = True
LOGIN_URL = '/saml2/login/'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SAML_CREATE_UNKNOWN_USER = True

SAML_CONFIG = {
    'debug': 1,
    'xmlsec_binary': '/usr/bin/xmlsec1',
    'entityid': 'http://simon.dev/saml2/metadata/',

    'allow_unknown_attributes': True,

    'service': {
        'sp': {
            'name': 'Test Userportal',
            'name_id_format': saml2.saml.NAMEID_FORMAT_PERSISTENT,
            'name_id_format_allow_create': True,

            'endpoints': {
                'assertion_consumer_service': [
                    ('http://localhost:8000/saml2/acs/', saml2.BINDING_HTTP_POST),
                ],
            },

            'signing_algorithm': saml2.xmldsig.SIG_RSA_SHA256,
            'digest_algorithm': saml2.xmldsig.DIGEST_SHA256,

            'required_attributes': [
                'surName',
                'givenName',
                'uid',
                'eduPersonAffiliation',
                'eduPersonPrincipalName',
                'displayName',
            ],

            # When set to true, the SP will consume unsolicited SAML
            # Responses, i.e. SAML Responses for which it has not sent
            # a respective SAML Authentication Request.
            'allow_unsolicited': False,
        },
    },

    'metadata': {
        'local': ['/opt/idp_metadata.xml'],  # need to remove the POST SingleSignOnService from shibboleth metadata, only redirect seems to work
    },

    # Signing
    'key_file': '/opt/private.key',  # private part
    'cert_file': '/opt/public.cert',  # public part

    # Encryption
    'encryption_keypairs': [{
        'key_file': '/opt/private.key',  # private part
        'cert_file': '/opt/public.cert',  # public part
    }],
}