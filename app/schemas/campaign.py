
from pydantic import BaseModel

class CampaignRequest(BaseModel):
    customer_name: str
    phone_number: str
    message_template: str
    offer_code: str
    expiry: str

class CampaignResponse(BaseModel):
    status: str
    delivery_time: str
