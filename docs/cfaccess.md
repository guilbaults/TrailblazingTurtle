# Cloudflare Access

`cfaccess` is a optional feature of TrailblazingTurtle developed and contributed by [ACENET](https://ace-net.ca) for use on [Siku](https://wiki.ace-net.ca/wiki/Siku).

To use it on your own cluster, you will need a Cloudflare Account and Access Subscription.

## How it Works

Cloudflare Access provides a cloud reverse proxy which can authenticate the User before requests can hit your application server.

When a request passes through Cloudflare Access, Cloudflare's reverse proxy will add a header (`Cf-Access-Jwt-Assertion`) and cookie (`CF_Authorization`) containing a [JWT](https://jwt.io/) (Json Web Token). The JWT is composed of Base64 encoded JSON signed by Cloudflare and contains attributes about the authenticated user.

Here is an example of the data encoded in the JWT:

```json
{
  "aud": [
    "32eafc7626e974616deaf0dc3ce63d7bcbed58a2731e84d06bc3cdf1b53c4228"
  ],
  "email": "user@example.com",
  "exp": 1659474457,
  "iat": 1659474397,
  "nbf": 1659474397,
  "iss": "https://yourteam.cloudflareaccess.com",
  "type": "app",
  "identity_nonce": "6ei69kawdKzMIAPF",
  "sub": "7335d417-61da-459d-899c-0a01c76a2f94",
  "country": "US"
}
```

You can learn more about the validation of the JWT [here](https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/validating-json/).

Custom attributes from the identity provider can also be passed in the JWT, such as `eduPersonPrincipalName` or Compute Canada specific attributes such as `ccServiceAccess`, . You can learn more about the validation of the JWT [here](https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/validating-json/).

## Configuration

You must configure your application to be accessable to Cloudflare. Cloudflare provides [Cloudflare Tunnels](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/), a daemon which connects out to the Cloudflare Network and tunnels traffic back to your application, no Public IP address required.

Configure your IDP(s) and Enable Cloudflare Access for your application.

You will need to select a attribute from your IDP, which matches the username in LDAP. For Alliance IDP, you can pass `eduPersonPrincipalName`, which for alliance users will be `<ldap uid>@alliancecan.ca`.

configuration your Cloudflare Access organization, Policy AUD, and Staff Attributes in `41-cloudflareaccess.py`.

You must:

  - Remove `djangosaml2.middleware.SamlSessionMiddleware` from `MIDDLEWARE`
  - Add `cfaccess.middleware.CloudflareAccessLDAPMiddleware` to `MIDDLEWARE`
  - Add `cfaccess.backends.CloudflareAccessLDAPBackend` to `AUTHENTICATION_BACKENDS`