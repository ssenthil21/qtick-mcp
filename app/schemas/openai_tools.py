
openai_tool_schemas = [
    {
        "name": "appointment.book",
        "description": "Books a new appointment in QTick.",
        "parameters": {
            "type": "object",
            "properties": {
                "business_id": {"type": "integer"},
                "customer_name": {"type": "string"},
                "service_id": {"type": "integer"},
                "datetime": {"type": "string"}
            },
            "required": ["business_id", "customer_name", "service_id", "datetime"]
        }
    },
    {
        "name": "appointment.list",
        "description": "List appointments for a business with optional filters.",
        "parameters": {
            "type": "object",
            "properties": {
                "business_id": {"type": "integer"},
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "status": {"type": "string"},
                "page": {"type": "integer"},
                "page_size": {"type": "integer"}
            },
            "required": ["business_id"]
        }
    },
    {
        "name": "invoice.create",
        "description": "Create an invoice for a customer with line items.",
        "parameters": {
            "type": "object",
            "properties": {
                "business_id": {"type": "integer"},
                "customer_name": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string"},
                            "description": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "unit_price": {"type": "number"},
                            "tax_rate": {"type": "number"}
                        },
                        "required": ["description", "quantity", "unit_price"]
                    }
                },
                "currency": {"type": "string"},
                "appointment_id": {"type": "string"},
                "notes": {"type": "string"}
            },
            "required": ["business_id", "customer_name", "items"]
        }
    },
    {
        "name": "leads.create",
        "description": "Create a new customer lead.",
        "parameters": {
            "type": "object",
            "properties": {
                "business_id": {"type": "integer"},
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "source": {"type": "string"},
                "notes": {"type": "string"}
            },
            "required": ["business_id", "name"]
        }
    },
    {
        "name": "campaign.sendWhatsApp",
        "description": "Sends a WhatsApp campaign message to a customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "phone_number": {"type": "string"},
                "message_template": {"type": "string"},
                "offer_code": {"type": "string"},
                "expiry": {"type": "string"}
            },
            "required": ["customer_name", "phone_number", "message_template", "offer_code", "expiry"]
        }
    },
    {
        "name": "analytics.report",
        "description": "Retrieves business analytics report for a given period.",
        "parameters": {
            "type": "object",
            "properties": {
                "business_id": {"type": "integer"},
                "metrics": {"type": "array", "items": {"type": "string"}},
                "period": {"type": "string"}
            },
            "required": ["business_id", "metrics", "period"]
        }
    }
]
