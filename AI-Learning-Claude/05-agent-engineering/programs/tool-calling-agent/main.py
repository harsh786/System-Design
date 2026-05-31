"""
Tool-Calling Agent using OpenAI Function Calling API
=====================================================
A customer service agent with 5 tools demonstrating parallel tool calls,
error handling, and a complete e-commerce scenario.
"""

import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =============================================================================
# TOOL IMPLEMENTATIONS (Simulated backend)
# =============================================================================

def get_weather(city: str) -> dict:
    """Simulated weather API for shipping estimates."""
    weather_data = {
        "new york": {"temp": 5, "condition": "snowy", "shipping_delay": "2 days"},
        "los angeles": {"temp": 22, "condition": "sunny", "shipping_delay": "none"},
        "chicago": {"temp": -2, "condition": "icy", "shipping_delay": "3 days"},
        "miami": {"temp": 28, "condition": "clear", "shipping_delay": "none"},
    }
    data = weather_data.get(city.lower())
    if data:
        return {"city": city, **data}
    return {"error": f"Weather data not available for {city}"}


def search_products(query: str, category: str = None) -> dict:
    """Simulated product catalog search."""
    catalog = [
        {"id": "P001", "name": "Wireless Headphones Pro", "category": "electronics", "price": 149.99, "rating": 4.5},
        {"id": "P002", "name": "Bluetooth Speaker Max", "category": "electronics", "price": 79.99, "rating": 4.2},
        {"id": "P003", "name": "Running Shoes Ultra", "category": "sports", "price": 129.99, "rating": 4.7},
        {"id": "P004", "name": "Yoga Mat Premium", "category": "sports", "price": 49.99, "rating": 4.8},
        {"id": "P005", "name": "Coffee Maker Deluxe", "category": "kitchen", "price": 199.99, "rating": 4.4},
    ]
    results = []
    for product in catalog:
        if query.lower() in product["name"].lower() or query.lower() in product["category"]:
            if category is None or product["category"] == category.lower():
                results.append(product)
    return {"results": results, "total": len(results)}


def calculate_price(product_id: str, quantity: int, discount_code: str = None) -> dict:
    """Calculate total price with optional discount."""
    prices = {"P001": 149.99, "P002": 79.99, "P003": 129.99, "P004": 49.99, "P005": 199.99}
    discounts = {"SAVE10": 0.10, "WELCOME20": 0.20, "VIP30": 0.30}

    if product_id not in prices:
        return {"error": f"Product {product_id} not found"}

    base = prices[product_id] * quantity
    discount_pct = discounts.get(discount_code, 0) if discount_code else 0
    discount_amount = base * discount_pct
    total = base - discount_amount

    return {
        "product_id": product_id,
        "quantity": quantity,
        "base_price": round(base, 2),
        "discount": f"{int(discount_pct * 100)}%",
        "discount_amount": round(discount_amount, 2),
        "total": round(total, 2),
    }


def check_inventory(product_id: str) -> dict:
    """Check stock availability."""
    inventory = {
        "P001": {"in_stock": True, "quantity": 45, "warehouse": "East"},
        "P002": {"in_stock": True, "quantity": 120, "warehouse": "West"},
        "P003": {"in_stock": False, "quantity": 0, "restock_date": "2024-02-15"},
        "P004": {"in_stock": True, "quantity": 200, "warehouse": "Central"},
        "P005": {"in_stock": True, "quantity": 8, "warehouse": "East"},
    }
    data = inventory.get(product_id)
    if data:
        return {"product_id": product_id, **data}
    return {"error": f"Product {product_id} not found in inventory system"}


def place_order(product_id: str, quantity: int, shipping_city: str) -> dict:
    """Place an order (simulated)."""
    if product_id == "P003":
        return {"error": "Product out of stock, cannot place order"}
    return {
        "order_id": f"ORD-{int(time.time())}",
        "product_id": product_id,
        "quantity": quantity,
        "shipping_city": shipping_city,
        "status": "confirmed",
        "estimated_delivery": "3-5 business days",
    }


# Tool function registry
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "search_products": search_products,
    "calculate_price": calculate_price,
    "check_inventory": check_inventory,
    "place_order": place_order,
}

# =============================================================================
# TOOL DEFINITIONS (for OpenAI API)
# =============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city. Use for shipping delay estimates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, e.g., 'New York'"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search the product catalog by name or category. Returns matching products with prices and ratings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term (product name or category)"},
                    "category": {"type": "string", "enum": ["electronics", "sports", "kitchen"], "description": "Optional category filter"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_price",
            "description": "Calculate total price for a product with quantity and optional discount code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Product ID like 'P001'"},
                    "quantity": {"type": "integer", "description": "Number of items"},
                    "discount_code": {"type": "string", "description": "Optional discount code like 'SAVE10'"},
                },
                "required": ["product_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_inventory",
            "description": "Check if a product is in stock and get quantity available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Product ID to check"}
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": "Place an order for a product. Only use after confirming stock and price with the customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Product ID to order"},
                    "quantity": {"type": "integer", "description": "Quantity to order"},
                    "shipping_city": {"type": "string", "description": "City to ship to"},
                },
                "required": ["product_id", "quantity", "shipping_city"],
            },
        },
    },
]

# =============================================================================
# AGENT LOOP
# =============================================================================

SYSTEM_PROMPT = """You are a helpful e-commerce customer service agent. You help customers:
- Find products
- Check prices and apply discounts
- Check inventory/availability
- Place orders
- Estimate shipping based on weather

Be concise and helpful. Use tools to get accurate information. Never guess prices or stock levels."""


def run_agent(user_message: str, max_turns: int = 10):
    """Run the tool-calling agent loop."""
    print("=" * 60)
    print(f"👤 Customer: {user_message}")
    print("=" * 60)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for turn in range(max_turns):
        start_time = time.time()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        elapsed = time.time() - start_time
        message = response.choices[0].message

        # If the model wants to call tools
        if message.tool_calls:
            print(f"\n  🔧 Tool calls (turn {turn + 1}, {elapsed:.2f}s):")
            messages.append(message)

            # Execute each tool call (may be parallel)
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                print(f"     → {fn_name}({json.dumps(fn_args)})")

                # Execute the tool
                tool_start = time.time()
                if fn_name in TOOL_FUNCTIONS:
                    try:
                        result = TOOL_FUNCTIONS[fn_name](**fn_args)
                    except Exception as e:
                        result = {"error": f"Tool execution failed: {str(e)}"}
                else:
                    result = {"error": f"Unknown tool: {fn_name}"}

                tool_elapsed = time.time() - tool_start
                print(f"       Result ({tool_elapsed:.3f}s): {json.dumps(result, indent=2)[:200]}")

                # Feed result back to the model
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })

        # If the model responds with text (no more tool calls)
        else:
            print(f"\n  🤖 Agent ({elapsed:.2f}s):")
            print(f"     {message.content}")
            return message.content

    print("\n  ⚠️  Max turns reached")
    return None


# =============================================================================
# MAIN - Demo scenarios
# =============================================================================

if __name__ == "__main__":
    scenarios = [
        # Scenario 1: Simple product search
        "I'm looking for headphones. What do you have?",

        # Scenario 2: Multi-step (search + inventory + price + order)
        "I want to buy 2 Wireless Headphones Pro with code SAVE10, ship to New York. Is it in stock? What's the total? Also check if there are shipping delays.",

        # Scenario 3: Error handling (out of stock)
        "I want to order the Running Shoes Ultra, ship to Chicago.",
    ]

    for scenario in scenarios:
        run_agent(scenario)
        print("\n" + "━" * 60 + "\n")
