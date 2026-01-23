"""
Google OAuth service for authentication.

Handles OAuth2/OpenID Connect flow with Google:
- Authorization URL generation
- Token exchange
- ID token validation with JWKS
- User profile extraction
"""
import os
import logging
from authlib.integrations.requests_client import OAuth2Session
from authlib.jose import jwt, JsonWebKey
from authlib.jose.errors import JoseError
import requests

logger = logging.getLogger(__name__)

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
GOOGLE_ISSUER = "https://accounts.google.com"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GoogleOAuthService:
    """Service for Google OAuth2/OpenID Connect authentication."""
    
    def __init__(self):
        """Initialize OAuth service with environment configuration."""
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GOOGLE_REDIRECT_URI')
        
        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            raise ValueError(
                "Missing Google OAuth configuration. "
                "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI"
            )
        
        logger.info(f"GoogleOAuthService initialized with redirect_uri: {self.redirect_uri}")
    
    def get_authorization_url(self, state):
        """
        Generate Google OAuth authorization URL.
        
        Args:
            state: CSRF protection token
        
        Returns:
            str: Authorization URL to redirect user to
        """
        session = OAuth2Session(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope='openid email profile'
        )
        
        authorization_url, _ = session.create_authorization_url(
            GOOGLE_AUTH_URL,
            state=state
        )
        
        logger.info(f"Generated authorization URL with state: {state[:10]}...")
        return authorization_url
    
    def exchange_code_for_tokens(self, code):
        """
        Exchange authorization code for access and ID tokens.
        
        Args:
            code: Authorization code from Google callback
        
        Returns:
            dict: Token response with 'access_token', 'id_token', etc.
        
        Raises:
            Exception: If token exchange fails
        """
        session = OAuth2Session(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri
        )
        
        try:
            token = session.fetch_token(
                GOOGLE_TOKEN_URL,
                code=code,
                client_secret=self.client_secret
            )
            
            logger.info("Successfully exchanged code for tokens")
            return token
            
        except Exception as e:
            logger.error(f"Token exchange failed: {str(e)}")
            raise
    
    def validate_and_decode_id_token(self, id_token):
        """
        Validate and decode ID token from Google.
        
        Performs comprehensive validation:
        - Signature verification with Google's public keys (JWKS)
        - Issuer validation
        - Audience validation
        - Expiration check
        - Email verification check
        
        Args:
            id_token: JWT ID token from Google
        
        Returns:
            dict: Decoded claims (sub, email, name, email_verified, etc.)
        
        Raises:
            ValueError: If token is invalid or verification fails
        """
        try:
            # Fetch Google's JWKS (public keys)
            jwks_uri = self._get_jwks_uri()
            jwks = self._fetch_jwks(jwks_uri)
            
            # Decode and validate token
            # authlib will automatically verify signature, exp, and standard claims
            claims = jwt.decode(id_token, jwks)
            
            # Validate issuer
            iss = claims.get('iss')
            if iss not in [GOOGLE_ISSUER, 'accounts.google.com']:
                raise ValueError(f"Invalid issuer: {iss}")
            
            # Validate audience
            aud = claims.get('aud')
            if aud != self.client_id:
                raise ValueError(f"Invalid audience: {aud}")
            
            # Validate email is verified
            email_verified = claims.get('email_verified')
            if not email_verified:
                raise ValueError("Email not verified by Google")
            
            logger.info(f"Successfully validated ID token for email: {claims.get('email')}")
            return claims
            
        except JoseError as e:
            logger.error(f"ID token validation failed (JOSE error): {str(e)}")
            raise ValueError(f"Token inválido: {str(e)}")
        except Exception as e:
            logger.error(f"ID token validation failed: {str(e)}")
            raise ValueError(f"Error validando token: {str(e)}")
    
    def _get_jwks_uri(self):
        """
        Get JWKS URI from Google's OpenID Connect discovery document.
        
        Returns:
            str: JWKS URI
        """
        try:
            response = requests.get(GOOGLE_DISCOVERY_URL, timeout=10)
            response.raise_for_status()
            discovery = response.json()
            jwks_uri = discovery.get('jwks_uri')
            
            if not jwks_uri:
                raise ValueError("No jwks_uri in discovery document")
            
            return jwks_uri
            
        except Exception as e:
            logger.error(f"Failed to fetch discovery document: {str(e)}")
            raise ValueError("Error obteniendo configuración de Google")
    
    def _fetch_jwks(self, jwks_uri):
        """
        Fetch JSON Web Key Set from Google.
        
        Args:
            jwks_uri: URI to fetch JWKS from
        
        Returns:
            JsonWebKey: JWKS for token validation
        """
        try:
            response = requests.get(jwks_uri, timeout=10)
            response.raise_for_status()
            jwks_data = response.json()
            
            # Convert to authlib JsonWebKey format
            return JsonWebKey.import_key_set(jwks_data)
            
        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {str(e)}")
            raise ValueError("Error obteniendo claves de Google")


# Singleton instance
_oauth_service = None

def get_google_oauth_service():
    """Get or create GoogleOAuthService singleton instance."""
    global _oauth_service
    if _oauth_service is None:
        _oauth_service = GoogleOAuthService()
    return _oauth_service
