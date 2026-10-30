import io
from pathlib import Path
import pandas as pd
import streamlit as st
from engine import COLUMNS, clean_data, calculate
from integrations import attach_distance, fetch_marketcheck, parse_facebook_text

st.set_page_config(page_title='Car Deal Finder', page_icon='🚗', layout='wide')
st.markdown('''<style>
.block-container{padding-top:2rem;max-width:1280px}
[data-testid="stMetricValue"]{font-size:1.7rem}
</style>''', unsafe_allow_html=True)
st.title('🚗 Car Deal Finder')
st.caption('Find undervalued Facebook Marketplace cars by comparing them with Facebook and other listed vehicles. Runs on your computer; no automated Facebook access.')

DATA = Path(__file__).parent / 'sample_listings.csv'
if 'data' not in st.session_state:
    st.session_state.data = pd.read_csv(DATA)

with st.sidebar:
    st.header('Search and settings')
    only_fb = st.toggle('Rank Facebook cars only', True)
    geo_on = st.toggle('Filter by distance', value=False)
    center_zip = st.text_input('Search center ZIP', value='75080', max_chars=5)
    radius = st.select_slider('Radius (miles)', options=[10,25,50,75,100,150,200],value=50)
    max_price = st.number_input('Maximum asking price ($)', 0, 1000000, 25000, 1000)
    min_year = st.number_input('Minimum model year', 1980, 2030, 2010)
    max_mileage = st.number_input('Maximum mileage', 0, 500000, 150000, 5000)
    makes = sorted(set(st.session_state.data['make'].dropna().astype(str))) if len(st.session_state.data) else []
    chosen_make = st.selectbox('Make', ['All'] + makes)
    st.divider()
    st.subheader('Comparison settings')
    min_comps = st.slider('Minimum comparable listings', 1, 10, 2)
    year_tol = st.slider('Model year tolerance (± years)', 0, 5, 2)
    mile_tol = st.slider('Mileage tolerance (± miles)', 5000, 80000, 35000, 5000)
    strict_trim = st.checkbox('Require exact trim match', value=False)
    facebook_weight = st.slider('Facebook share of price estimate', 0, 100, 75, 5)/100

upload_tab, add_tab, fb_tab, live_tab, help_tab = st.tabs(['📤 Upload / manage data', '➕ Add a listing', '📋 Paste Facebook listing', '🌐 Live inventory', 'ℹ️ How it works'])
with upload_tab:
    uploaded = st.file_uploader('Upload listings CSV (Facebook, CarGurus, CarMax, etc.)', type=['csv'])
    if uploaded is not None:
        try:
            new = clean_data(pd.read_csv(uploaded))
            if st.button(f'Add {len(new)} valid rows to dataset'):
                st.session_state.data = pd.concat([st.session_state.data, new[COLUMNS]],ignore_index=True)
                st.success('Listings added.')
        except Exception as exc: st.error(f'Could not read CSV: {exc}')
    a,b,c = st.columns(3)
    with a: st.download_button('Download CSV template',DATA.read_bytes(),'car_listings_template.csv','text/csv')
    with b: st.download_button('Export current dataset',st.session_state.data.to_csv(index=False),'my_car_listings.csv','text/csv')
    with c:
        if st.button('Reset to demo data'):
            st.session_state.data = pd.read_csv(DATA)
            st.rerun()
    st.caption('Demo records are fictional. The system does NOT search Facebook automatically.')
    with st.expander('View/edit current dataset'):
        edited = st.data_editor(st.session_state.data, num_rows='dynamic', use_container_width=True, key='data_editor')
        if st.button('Save table edits'):
            st.session_state.data = clean_data(edited)[COLUMNS]
            st.rerun()
with add_tab:
    with st.form('add_listing',clear_on_submit=True):
        c1,c2,c3,c4 = st.columns(4)
        source = c1.selectbox('Source',['Facebook Marketplace','CarGurus','CarMax','Other'])
        year = c2.number_input('Year',1980,2030,2018)
        make = c3.text_input('Make',placeholder='Honda')
        model = c4.text_input('Model',placeholder='Civic')
        c1,c2,c3,c4 = st.columns(4)
        trim = c1.text_input('Trim',placeholder='EX')
        mileage = c2.number_input('Mileage',0,1000000,75000)
        price = c3.number_input('Price ($)',1,1000000,12000)
        zip_code = c4.text_input('ZIP code',placeholder='75080')
        title = st.selectbox('Title status',['','Clean','Rebuilt','Salvage','Unknown'])
        desc = st.text_area('Seller description')
        url = st.text_input('Listing URL')
        if st.form_submit_button('Add listing',type='primary'):
            if not make.strip() or not model.strip(): st.error('Make and model are required.')
            else:
                record={'source':source,'year':year,'make':make,'model':model,'trim':trim,'mileage':mileage,'price':price,'zip_code':zip_code,'title_status':title,'description':desc,'url':url,'date_seen':pd.Timestamp.now().date().isoformat()}
                st.session_state.data = pd.concat([st.session_state.data,pd.DataFrame([record])],ignore_index=True)
                st.success('Listing added. Scroll down for results.')
with fb_tab:
    st.write('Copy the visible text of a Facebook listing you are allowed to view and paste it here. This app does **not** visit Facebook or scrape listings. Add the listing ZIP if it is not included in the description.')
    pasted = st.text_area('Paste listing text (start with e.g. 2018 Honda Civic, include $price and mileage)',height=180)
    pasted_zip = st.text_input('Listing ZIP (optional if text contains ZIP)',value=center_zip,key='fb_zip')
    if st.button('Import pasted Facebook listing',type='primary'):
        try:
            row=parse_facebook_text(pasted,pasted_zip)
            st.session_state.data=clean_data(pd.concat([st.session_state.data,pd.DataFrame([row])],ignore_index=True))[COLUMNS]
            st.success(f"Added {row['year']} {row['make']} {row['model']}.")
        except Exception as exc: st.error(str(exc))
    st.caption('Do not share passwords, cookies, messages with sellers, or other private information.')
with live_tab:
    st.write('Search active MarketCheck dealer inventory or private-seller inventory with your own API key. Results are imported into the comparison dataset. Private-seller access may require a paid subscription.')
    api_key = st.text_input('MarketCheck API key',type='password',value='',help='Enter a key from developers.marketcheck.com. Stored only in current Streamlit session while the app runs.')
    source_choice = st.selectbox('Inventory source',['Dealer','Private seller'])
    c1,c2,c3=st.columns(3)
    live_make=c1.text_input('Make (optional)',placeholder='Honda')
    live_model=c2.text_input('Model (optional)',placeholder='Civic')
    live_rows=c3.number_input('Results per page',min_value=1,max_value=50,value=25)
    live_pages=st.number_input('Maximum pages (up to 5)',min_value=1,max_value=5,value=1)
    st.caption(f'Search ZIP {center_zip} within {radius} miles. Uses maximum asking price ${max_price:,} from sidebar. API calls may be billed.')
    if st.button('Fetch live inventory',type='primary'):
        try:
            with st.spinner('Requesting authorized inventory data…'):
                records=fetch_marketcheck(api_key,center_zip,radius,max_price,live_make,live_model,
                     'private' if source_choice=='Private seller' else 'dealer',live_rows,live_pages)
            if records:
                before=len(clean_data(st.session_state.data))
                st.session_state.data=clean_data(pd.concat([st.session_state.data,pd.DataFrame(records)],ignore_index=True))[COLUMNS]
                st.success(f'Received {len(records)} listings. Dataset now has {len(st.session_state.data)} listings (previously {before}); duplicate links were removed.')
            else: st.info('No listings returned. Try different search filters or check API access.')
        except Exception as exc:
            st.error(f'Inventory request failed: {exc}. Check API key, endpoint access, and usage limits.')
with help_tab:
    st.markdown('''**How to use:** Collect listings you are authorized to access, save their facts to CSV, and import them here. Add Facebook listings and independent listings for the *same make and model* to obtain comparisons. The demo dataset is fictional.

**Scoring:** Comps match make/model, similar year and mileage. The app adjusts asking prices by a simple $0.055/mile and $850/model-year heuristic, then blends Facebook and other-source medians using your sidebar weight. These assumptions are illustrative, not professional valuations. Risks use description keywords, not vehicle inspections. A low asking price is not guaranteed profit.

**Location:** Enable the distance filter in the sidebar. ZIP centroid coordinates are fetched using Zippopotam.us and haversine distance. Missing/unresolved listing ZIPs are excluded, not treated as nearby. Distances are approximate straight-line miles, not driving distance.

**Important:** Never bypass Facebook access controls. This app does not scrape sites, validate VINs, verify title status, or confirm seller authenticity. All prices are *asking* prices, not completed sales.
''')

st.divider()
st.subheader('🏆 Ranked deals')
data = clean_data(st.session_state.data)
if data.empty:
    st.info('Add some listings to get started.')
else:
    if geo_on:
        try:
            data, missing_count=attach_distance(data,center_zip,radius)
            st.caption(f'Location filter: {len(data)} listings within ~{radius} straight-line miles of ZIP {center_zip}; {missing_count} omitted because their ZIP could not be resolved.')
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
    scored = calculate(data, focus='Facebook Marketplace' if only_fb else 'All',min_comps=min_comps,year_tolerance=year_tol,miles_tolerance=mile_tol,trim_match=strict_trim,facebook_weight=facebook_weight)
    if scored.empty:
        st.warning('No cars have enough comparable listings. Add more cars of the same make/model or loosen the matching filters.')
    else:
        scored = scored[(scored.price<=max_price)&(scored.year>=min_year)&(scored.mileage<=max_mileage)]
        if chosen_make != 'All': scored = scored[scored.make==chosen_make]
        a,b,c = st.columns(3)
        a.metric('Matching candidates',len(scored))
        b.metric('Below estimated market',int((scored.discount_dollars>0).sum()))
        c.metric('Largest estimated discount',f"${max(0,scored.discount_dollars.max()):,.0f}" if len(scored) else '$0')
        viewcols = ['year','make','model','trim','mileage','price','estimated_market','discount_dollars','discount_pct','deal_score','confidence','facebook_comps','external_comps','flags','url']
        st.dataframe(scored[viewcols],hide_index=True,use_container_width=True,column_config={'price':st.column_config.NumberColumn('Asking price',format='$%d'),'estimated_market':st.column_config.NumberColumn('Estimated market',format='$%d'),'discount_dollars':st.column_config.NumberColumn('Estimated discount',format='$%d'),'discount_pct':st.column_config.NumberColumn('Below market %',format='%.1f%%'),'url':st.column_config.LinkColumn('Open listing')})
        st.download_button('⬇️ Export ranked deals',scored.to_csv(index=False),'ranked_car_deals.csv','text/csv')
        st.caption('Estimates use asking prices, not sale prices. Demo listings are fictional; MarketCheck imports are live at time of retrieval. ZIP radius uses approximate straight-line distances.')
        st.subheader('Inspect a candidate')
        selected = st.selectbox('Choose listing',range(len(scored)),format_func=lambda i:f"{scored.iloc[i]['year']} {scored.iloc[i]['make']} {scored.iloc[i]['model']} — ${scored.iloc[i]['price']:,.0f} ({scored.iloc[i]['source']})") if len(scored) else None
        if selected is not None:
            x = scored.iloc[selected]
            aa,bb,cc = st.columns(3)
            aa.metric('Asking price',f"${x.price:,.0f}")
            bb.metric('Comparable market estimate',f"${x.estimated_market:,.0f}")
            cc.metric('Estimated difference',f"${x.discount_dollars:,.0f}",f"{x.discount_pct:.1f}% below market")
            st.write(f"**Comparables:** {x.facebook_comps} Facebook, {x.external_comps} external  |  **Confidence heuristic:** {x.confidence}/100")
            st.write(f"**Potential concerns:** {x['flags']}")
            st.write(f"**Description:** {x.description or 'Not provided'}")
            if str(x.url).startswith(('https://','http://')): st.link_button('Open original listing',str(x.url))
