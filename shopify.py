"""
Shopify API integration utilities
Uses proper OAuth access tokens and required scopes
"""
import httpx
from typing import Optional, Dict, Any, List
from config import settings
from database import AccessToken


class ShopifyClient:
    """Client for interacting with Shopify Admin API with OAuth"""
    
    def __init__(self, shop_domain: Optional[str] = None):
        self.shop_domain = shop_domain or settings.SHOPIFY_SHOP_DOMAIN
        self.api_key = settings.SHOPIFY_API_KEY
        self.api_secret = settings.SHOPIFY_API_SECRET
        self.base_url = f"https://{self.shop_domain}"
        self.api_version = "2024-01"
    
    async def get_access_token(self) -> Optional[str]:
        """
        Retrieve access token for shop domain from database
        Falls back to config SHOPIFY_ADMIN_ACCESS_TOKEN if no OAuth token found
        """
        token = await AccessToken.find_one(AccessToken.shop == self.shop_domain)
        if token:
            return token.access_token
        # Fallback to config access token if available
        return settings.SHOPIFY_ADMIN_ACCESS_TOKEN
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        access_token: Optional[str] = None,
        data: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Make authenticated request to Shopify Admin API"""
        token = access_token or await self.get_access_token()
        if not token:
            raise ValueError("Access token required. App must be installed via OAuth.")
        
        url = f"{self.base_url}/admin/api/{self.api_version}/{endpoint}"
        headers = {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = await client.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                response = await client.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if response.status_code == 200 or response.status_code == 201:
                return response.json()
            elif response.status_code == 401:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get('errors', error_detail)
                except:
                    pass
                raise ValueError(f"Invalid access token or insufficient scopes: {error_detail}")
            else:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get('errors', error_json.get('error', error_detail))
                except:
                    pass
                print(f"Shopify API Error - Status: {response.status_code}, URL: {url}, Response: {error_detail}")
                raise ValueError(f"Shopify API error ({response.status_code}): {error_detail}")
    
    async def get_customer(
        self,
        customer_id: int,
        access_token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch customer data from Shopify
        Requires: read_customers scope
        """
        try:
            result = await self._make_request(
                "GET",
                f"customers/{customer_id}.json",
                access_token
            )
            return result.get("customer") if result else None
        except Exception as e:
            print(f"Error fetching customer: {e}")
            return None
    
    async def update_customer(
        self,
        customer_id: int,
        customer_data: Dict[str, Any],
        access_token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update customer data in Shopify
        Requires: write_customers scope
        """
        try:
            result = await self._make_request(
                "PUT",
                f"customers/{customer_id}.json",
                access_token,
                {"customer": customer_data}
            )
            return result.get("customer") if result else None
        except Exception as e:
            print(f"Error updating customer: {e}")
            return None
    
    async def get_subscription_contracts(
        self,
        customer_id: int,
        access_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get subscription contracts for a customer
        Requires: read_own_subscription_contracts scope
        Uses GraphQL Admin API
        """
        # GraphQL query for subscription contracts
        query = """
        query getCustomerSubscriptions($customerId: ID!) {
            customer(id: $customerId) {
                subscriptionContracts(first: 10) {
                    edges {
                        node {
                            id
                            status
                            nextBillingDate
                            lines(first: 10) {
                                edges {
                                    node {
                                        title
                                        quantity
                                        currentPrice {
                                            amount
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        # TODO: Implement GraphQL request
        # For now, return empty list
        return []
    
    async def create_subscription_contract(
        self,
        customer_id: int,
        product_id: str,
        variant_id: str,
        quantity: int = 1,
        access_token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a subscription contract
        Requires: write_own_subscription_contracts scope
        Uses GraphQL Admin API
        """
        # TODO: Implement GraphQL mutation
        # mutation createSubscriptionContract {
        #   subscriptionContractCreate(...) { ... }
        # }
        return None
    
    async def get_orders(
        self,
        customer_id: Optional[int] = None,
        limit: int = 50,
        access_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get orders from Shopify
        Requires: read_orders scope
        """
        try:
            # Build query parameters
            params = [f"limit={limit}"]
            if customer_id:
                params.append(f"customer_id={customer_id}")
            
            # Add status filter to get all orders (including archived)
            params.append("status=any")
            
            endpoint = f"orders.json?{'&'.join(params)}"
            
            result = await self._make_request("GET", endpoint, access_token)
            if result:
                orders = result.get("orders", [])
                print(f"Successfully fetched {len(orders)} orders from Shopify")
                return orders
            return []
        except Exception as e:
            print(f"Error fetching orders: {e}")
            import traceback
            traceback.print_exc()
            raise ValueError(f"Failed to fetch orders: {str(e)}")
    
    async def list_customers(
        self,
        limit: int = 50,
        access_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all customers from Shopify
        Requires: read_customers scope
        """
        try:
            result = await self._make_request(
                "GET",
                f"customers.json?limit={limit}",
                access_token
            )
            return result.get("customers", []) if result else []
        except Exception as e:
            print(f"Error fetching customers: {e}")
            return []
    
    async def list_products(
        self,
        limit: int = 50,
        access_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all products from Shopify
        Requires: read_products scope
        """
        try:
            result = await self._make_request(
                "GET",
                f"products.json?limit={limit}",
                access_token
            )
            return result.get("products", []) if result else []
        except Exception as e:
            print(f"Error fetching products: {e}")
            return []
    
    async def create_product(
        self,
        product_data: Dict[str, Any],
        access_token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new product in Shopify
        Requires: write_products scope
        """
        try:
            result = await self._make_request(
                "POST",
                "products.json",
                access_token,
                {"product": product_data}
            )
            return result.get("product") if result else None
        except Exception as e:
            print(f"Error creating product: {e}")
            raise ValueError(f"Failed to create product: {str(e)}")
    
    async def get_shop_info(
        self,
        access_token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get shop information
        Requires: read_products scope (or any read scope)
        """
        try:
            result = await self._make_request("GET", "shop.json", access_token)
            return result.get("shop") if result else None
        except Exception as e:
            print(f"Error fetching shop info: {e}")
            return None


# Global client instance (uses default shop domain from settings)
shopify_client = ShopifyClient()

# Factory function to create client for specific shop
def get_shopify_client(shop_domain: str) -> ShopifyClient:
    """Create Shopify client for specific shop domain"""
    return ShopifyClient(shop_domain=shop_domain)

