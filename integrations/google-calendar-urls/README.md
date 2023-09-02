# Cosmos Upgrades to Google Calendar 🌌📅

Integrate with the `cosmos-upgrades` API to fetch upgrade events and add them to your Google Calendar with a single click.

## Features 🚀

- Fetches upgrade events from the `cosmos-upgrades` API for both mainnets and testnets.
- Automatically creates Google Calendar events for each upgrade.
- Provides direct links to the relevant block details on Mintscan.

## Prerequisites 📜

1. Python 3.6+
2. `requests` library (install via pip)

## Setup & Installation ⚙️

1. Clone the repository:
   ```bash
   git clone <repository_url>
   ```

2. Install required packages:
   ```bash
   pip install requests
   ```

3. Run the tool:
   ```bash
   python <filename>.py
   ```

## Customizing Monitored Networks 🎛️

By default, the tool monitors a preset list of mainnets and testnets. If you're interested in specific networks, you can easily customize the list:

1. Open `app.py` in your preferred code editor.
   
2. Locate the `networks` dictionary:

    ```python
    networks = {
        "mainnets": "...",
        "testnets": "..."
    }
    ```

3. Modify the list of networks under `mainnets` or `testnets` as required. Ensure network names are separated by a space.

   For example, to only monitor the `osmosis` and `akash` mainnets:

   ```python
   "mainnets": "osmosis akash",
   ```

4. Save the file and run the tool.

## Usage 💡

1. Run the tool.
2. For each upgrade event fetched, you'll receive a link in the console.
3. Click on the link to open Google Calendar and create an event for the upgrade.
4. Save the event to be reminded of the upcoming upgrade!

## Code Overview 🧠

- `get_events_from_api()`: Fetches the upgrade events from the `cosmos-upgrades` API.
  
- `create_google_calendar_event(event_data)`: Takes the event data, formats it, and provides a URL to create the event in Google Calendar.
  
- `main()`: Primary function that orchestrates the fetching and calendar event creation.

## Support & Contributions 🤝

For any issues or feature requests, open an issue in this repository or submit a pull request. Contributions are welcomed!

## Disclaimer ⚠️

The tool depends on the `cosmos-upgrades` API for its data. Ensure you verify any critical events manually to avoid any discrepancies.

## License 📄

This project is open-source. Feel free to use, modify, and distribute as you see fit.

---

Happy scheduling! 🌌🎉