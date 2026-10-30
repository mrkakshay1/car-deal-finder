# Car Deal Finder — Working prototype

A local Streamlit dashboard that compares user-supplied Facebook Marketplace used-car listings to other Facebook listings and outside sources. It ranks estimated discounts, flags suspicious description terms, and exports ranked results.

## Quick start (Windows / macOS / Linux)

1. Install Python 3.10 or newer from https://python.org . On Windows select **Add Python to PATH**.
2. Download/extract this project and open a terminal in the `car_deal_finder` folder.
3. Run:

   ```bash
   python -m pip install -r requirements.txt
   python -m streamlit run app.py
   ```

4. Streamlit normally opens http://localhost:8501 in your web browser.
5. Try the demo results, add a listing manually, or upload a CSV.

If `python` does not work on Windows, try `py` in both commands.

## Data fields

`source,year,make,model,trim,mileage,price,zip_code,title_status,description,url,date_seen`

`source` should identify Facebook Marketplace (contains "Facebook") or e.g. CarGurus, CarMax, Other. Each CSV row is one listing. URLs may be left empty. Include **several comparable cars for each make/model**. There are no live listings included: all demo cars are fictional and have no URL.

## What it does and does not do

- ✅ CSV import/export; add and edit listings; rank Facebook or all cars.
- ✅ Matches make/model/year/mileage, mileage and age adjustment, Facebook-weighted estimate, heuristic risk flags.
- ✅ Allows price, model year, mileage, and make filters.
- ❌ No Facebook scraping or automatic fetching. Obtain listings only in authorized ways.
- ❌ No live CarGurus/CarMax integration; external listings must be uploaded or entered.
- ❌ ZIP search radius filtering is **not available** in this version. Limit the imported listings to your geography. ZIP is kept for future integration.
- ❌ No AI API calls yet: built-in keyword-based risk checks are deterministic. An optional LLM description analysis can be added later.
- ❌ No persistence after restarting Streamlit. Export your CSV to save your changes.

## Estimation

Eligible comps match make/model and configurable year and mileage ranges. Their asking prices are adjusted by `0.055 * (comp_miles - target_miles)` and `850 * (target_year - comp_year)`, then source medians are blended. These **arbitrary starting heuristics** need calibration against real data. The ranking is not an appraised fair market value, confirmed selling price, or verified profit. Inspect vehicles and verify titles before purchasing.

## Next version priorities

1. Authorized live automotive inventory data source and automated imports.
2. ZIP geocoding and actual radius filters.
3. Better calibrated regressions per make/model and separate private-party/dealer pricing.
4. Duplicate detection, VIN lookups, vehicle history integration, and verified risk signals.
5. Optional LLM API for extracting information from listing descriptions and notifications for new deals.

## Version 2 additions: live inventory, distance, permitted Facebook import

1. Use the sidebar **Filter by distance**, enter US ZIP and radius. The app uses public Zippopotam.us geocoding for the ZIP centroid, then approximate great-circle miles (not driving distance). The service needs an internet connection. Unknown ZIPs are excluded; geocoding failures are shown explicitly. The filter is applied **before** comparable selection, so geographic comparisons are local as well.
2. Under **Paste Facebook listing**, paste text you personally have permission to use, starting with a line like `2018 Honda Civic`, followed by a price such as `$12000` and mileage such as `75000 miles`, and optional `ZIP: 75080`, `Title: Clean`, `Trim: EX`, and Facebook listing URL. Nothing is fetched from Facebook; pasted information is not independently verified.
3. Under **Live inventory**, obtain an API key from https://developers.marketcheck.com/ and enter it in the UI (not in code). Choose **Dealer** or **Private seller**, optional make/model, and Fetch. MarketCheck API endpoint access and billing depend on your account. Private party endpoint may be higher priced. Dealer and private-party listings are not guaranteed to include any particular website. Facebook source names are only assigned where a Facebook URL is present.
4. Download CSV before closing if you want to keep imported data. Entries remain session-only and are not written to disk by the app.

### Endpoint references
- Dealer: https://docs.marketcheck.com/docs/api/cars/inventory/inventory-search (`GET /v2/search/car/active`)
- Private seller: https://docs.marketcheck.com/docs/api/cars/inventory/private-party-search (`GET /v2/search/car/fsbo/active`)
- ZIP lookup: https://api.zippopotam.us/

**Cautions:** API keys are held in Streamlit widget memory and sent only to MarketCheck when fetching. Avoid deploying a public app with a shared key unless you configure authentication/quotas. No scraping or unapproved data extraction is performed. Prices, seller descriptions and title status are not independently verified. All valuation adjustments are heuristic starting points.
