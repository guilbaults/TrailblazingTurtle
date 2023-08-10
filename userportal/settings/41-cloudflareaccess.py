# Cloudflare Authentication is Disabled by default
# For instructions to enable, see docs/cfaccess.md

CF_ACCESS_CONFIG = {
    'team_domain': 'https://<your-org>.cloudflareaccess.com',
    'policy_aud': 'get-this-from-cloudflare-dashboard',

    'username_attribute': 'email',
    ''

    # if this option is true, all requests that do not contain a valid JWT will get a 403 Forbidden
    'enforce_cloudflare_access': False,

    # Use this to assign the staff role based on attributes from the Cloudflare JWT.
    # If ANY one of these attributes match, user is_staff will be set to True
    'staff_attributes': [
        ('ccServiceAccess', '<your-cluster>-portal-staff')
    ]
}