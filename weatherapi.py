import requests

# 🔹 Function to get the weather forecast for a specific location and date using OpenWeather API
def find_weather_forecast(date, location, openweather_api_key):
    base_url = "https://api.openweathermap.org/data/2.5/forecast"

    # Make a request to OpenWeather API with the location and date
    params = {
        'q': location,   # Location name (e.g., 'San Juan, PR')
        'appid': openweather_api_key,  # API key loaded from file
        'units': 'metric',  # Temperature in Celsius (this will be converted to Fahrenheit later)
        'cnt': '40',  # Number of forecasts to fetch (8 forecasts per day for 5 days)
    }

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        data = response.json()

        # Check for available forecasts for the requested date
        for forecast in data['list']:
            if forecast['dt_txt'].startswith(date):  # Date format: "YYYY-MM-DD"
                # Convert temperature from Celsius to Fahrenheit
                temp_fahrenheit = (forecast['main']['temp'] * 9/5) + 32
                feels_like_fahrenheit = (forecast['main']['feels_like'] * 9/5) + 32

                # Return the data along with the units
                return {
                    'temp': {'value': temp_fahrenheit, 'unit': '°F'},
                    'feels_like': {'value': feels_like_fahrenheit, 'unit': '°F'},
                    'temp_min': {'value': (forecast['main']['temp_min'] * 9/5) + 32, 'unit': '°F'},
                    'temp_max': {'value': (forecast['main']['temp_max'] * 9/5) + 32, 'unit': '°F'},
                    'pressure': {'value': forecast['main']['pressure'], 'unit': 'hPa'},
                    'sea_level': {'value': forecast['main']['sea_level'], 'unit': 'hPa'},
                    'grnd_level': {'value': forecast['main']['grnd_level'], 'unit': 'hPa'},
                    'humidity': {'value': forecast['main']['humidity'], 'unit': '%'},
                    'weather': forecast['weather'][0]['description']
                }

        return "No forecast available for this date."
    else:
        return "Error fetching data from OpenWeather API."
    

from datetime import datetime, timedelta

# 🔹 List of valid Puerto Rican municipalities (78 municipalities) in lowercase
valid_locations = [
    "adjuntas", "aguada", "aguadilla", "aguas buenas", "aibonito", "añasco", "arecibo", "arroyo", "barceloneta", "barranquitas",
    "bayamón", "cabo rojo", "caguas", "camuy", "canóvanas", "carolina", "cataño", "cayey", "ceiba", "ciales", "cidra", "coamo",
    "comerío", "corozal", "culebra", "dorado", "fajardo", "florida", "guánica", "guayama", "guayanilla", "guaynabo", "gurabo",
    "hatillo", "hormigueros", "humacao", "isabela", "jayuya", "juana díaz", "juncos", "lajas", "lares", "las marías", "las piedras",
    "loíza", "luquillo", "manatí", "maricao", "maunabo", "mayagüez", "moca", "morovis", "naguabo", "naranjito", "orocovis", "patillas",
    "peñuelas", "ponce", "quebradillas", "rincón", "río grande", "sabana grande", "salinas", "san germán", "san juan", "san lorenzo",
    "san sebastián", "santa isabel", "toa alta", "toa baja", "trujillo alto", "utuado", "vega alta", "vega baja", "vieques", "villalba",
    "yabucoa", "yauco"
]

# 🔹 Mapping variations of municipalities with special characters or spaces to their canonical names
location_mapping = {
    "anasco": "añasco", "bayamon": "bayamón", "canovanas": "canóvanas", "catano": "cataño",
    "comerio": "comerío", "guanica": "guánica", "juana diaz": "juana díaz", "las marias": "las marías",
    "loiza": "loíza", "manati": "manatí", "mayaguez": "mayagüez", "penuelas": "peñuelas", "rincon": "rincón",
    "rio grande": "río grande", "san german": "san germán", "san sebastian": "san sebastián", "juanadiaz": "juana díaz",
    "lasmarias": "las marías", "laspiedras": "las piedras", "riogrande": "río grande", "sabanagrande": "sabana grande",
    "sangerman": "san germán", "sanjuan": "san juan", "sanlorenzo": "san lorenzo", "sansebastian": "san sebastián",
    "santaisabel": "santa isabel", "toaalta": "toa alta", "toabaja": "toa baja", "trujilloalto": "trujillo alto",
    "vegaalta": "vega alta", "vegabaja": "vega baja"
}

# 🔹 Function to validate the date format (YYYY-MM-DD) and ensure it's within the next 5 days
def validate_date(date):
    try:
        valid_date = datetime.strptime(date, "%Y-%m-%d")
        today = datetime.today()
        if valid_date < today or valid_date > today + timedelta(days=5):
            return None  # Out of the valid date range (more than 5 days ahead)
        return valid_date
    except ValueError:
        return None

# 🔹 Function to normalize and validate location (case-insensitive, check for valid locations)
def validate_location(location):
    # Remove extra spaces and convert to lowercase
    location = location.strip().lower()

    # Replace location variations with their canonical names
    for key, value in location_mapping.items():
        if key in location:
            location = value
            break  # Stop checking further once a match is found

    # Normalize input by handling cases like 'San Juan', 'san juan', 'San Juan, PR'
    if location.endswith(", pr"):
        location = location.replace(", pr", "")  # Remove the ", pr" part for simpler comparison

    # Check if location is in the list of valid Puerto Rican municipalities
    if location in valid_locations:
        return location.capitalize()  # Return the location with proper capitalization

    return None  # If not found, return None

# 🔹 Function to validate weather preferences and handle contradictory preferences (e.g., 'sunny' and 'rainy')
def validate_weather_preferences(user_preferences):
    invalid_preferences = ["snow", "foggy"]
    contradictory_preferences = {"sunny", "rainy"}

    # Check for unrealistic weather preferences
    if any(pref in invalid_preferences for pref in user_preferences):
        print("Error: This weather condition is not typical in Puerto Rico.")
        return False

    # Check for contradictory preferences
    if contradictory_preferences.issubset(set(user_preferences)):
        print("Warning: You’ve selected both sunny and rainy preferences. The system will prioritize the forecasted condition.")

    return True



# 🔹 Function to handle complex preferences and edge cases, including user input errors
def get_weather(date, location, openweather_api_key):
    valid_date = validate_date(date)
    # Validate location (check if it's a valid Puerto Rican municipality)
    validated_location = validate_location(location)

    
    forecast = find_weather_forecast(date, location, openweather_api_key)
    # Generate the recommendation based on the weather
    if forecast == "No forecast available for this date.":
        return "No forecast available for this date."
    elif forecast == "Error fetching data from OpenWeather API.":
        return "Error fetching data from OpenWeather API."
    else:
        return forecast
