edX Alexa Skills
----------------

We are currently using `Flask-Ask <https://github.com/johnwheeler/flask-ask/>`_ and
`Zappa <https://github.com/Miserlou/Zappa>`_ to deploy to AWS S3 and Lambda.

Current Capabilities
====================

- Get info on edX
- List current enrollments
- Find courses about a particular subject

TODO: Configuration
===================
* AWS IAM roles/permissions
* Setup two API clients—one for login, one for service requests (e.g. search)—due to the inability to instruct
  Amazon to get a JWT token.

TODO: Deployment
================
* Getting Zappa setup is tedious, and ultimately ends up in granting the user too many privileges
* Need to find a secure location to store `dev-config.json`
* Deployment pipeline?
