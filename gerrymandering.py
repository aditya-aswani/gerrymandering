# -*- coding: utf-8 -*-
"""
The Gerrymandering Project
Navo, Morgan, Jay, Charet

Last Updated: 12/18/20
"""


!pip install chromedriver_autoinstaller
!pip install osgeo
!pip install plotly-geo
!pip install geopandas==0.3.0
!pip install pyshp==1.2.10
!pip install shapely==1.6.3

from selenium import webdriver
import chromedriver_autoinstaller
chromedriver_autoinstaller.install()
import numpy as np
import pandas as pd
import json
import requests
import io
import sys
import os
from os import path
from plotly.offline import plot
import plotly.figure_factory as ff
import plotly.express as px
import PySimpleGUI as sg
import time
import re
import sqlite3
from bs4 import BeautifulSoup

# defines function that inputs user information into a web browser and then scrapes representative data based on inputted address
def district_finder(street, city, state, zipcode):
    #access the chrome driver to access districts site
    try:
        try:
            #opens chrome webdriver
            driver = webdriver.Chrome()
            driver.get('https://openstates.org/find_your_legislator/')
     #inputs address and submits entry
            address = driver.find_element_by_id('fyl-address')
            address.send_keys(str(street + ', ' + city + ', ' + state + ', ' + zipcode))
            time.sleep(5)
        except Exception:
            sg.popup('Error! Please Wait A Moment. You Closed Selenium. Python Will Restart!')
            window.close()
            main()
        
        #automatically click address lookup button
        addressclick = driver.find_element_by_id('address-lookup')
        addressclick.click()
        time.sleep(5)
        link = driver.current_url
        #appends representatives information and returns lower district number 
        data = []
        for tr in driver.find_elements_by_xpath('//table[@id="results"]//tr'):
            tds = tr.find_elements_by_tag_name('td')
            if tds: 
                data.append([td.text for td in tds])
        df = pd.DataFrame(data, columns = ['pic','NAME','PARTY','DISTRICT','CHAMBER'])
        df.drop(columns='pic')
        upper = df[df["CHAMBER"] == "upper"]
        upperdistrict = upper.iloc[[0],[3]]
        lower = df[df["CHAMBER"] == "lower"]
        lowerdistrict = lower.iloc[[0],[3]]
        disno = lowerdistrict.iloc[0]['DISTRICT']
        return disno
    except Exception:
        sg.PopupError('Please Wait A Moment.')
        window.close() 
        main()
      
'''
Input: A user's district number
Output 1 (str): If user's district is at least moderately gerrymandered, it will
output the individual's representative, their contact information, and a
call template to say to their representative

Output 2 (str): If user's district is not at least moderately gerrymandered, the 
program will output information on national representatives and encourage the 
individual to advocate for gerrymandering in general
'''


#webscrape for representative phone number
def repPhone(disno):
    repinfo = requests.get\
        ('https://www.pahouse.com/' + disno + '/Contact/')
    soup = BeautifulSoup(repinfo.content, 'html.parser')
    try: 
        PageContents = soup.find(id = 'Contact-Office-Info')
        ContactInfo = PageContents.find(class_ = 'officeInfoDIV pl-4 col-lg-offset-1 col-lg-10 col-12')
        PrimaryContact = ContactInfo.find(title = 'Primary Phone')
        Phone = PrimaryContact.find_next('a')
        return str('A prompt has been provided that will persuade your representative to help end gerrymandering. Show your support today and give your representative a call at' + Phone.text + '. In addition to the script, you also have a gerrymandering map saved in your folder called temp-plot.html')
    except Exception:
        sg.PopupError('Since your representative does not have contact information at this time, Python will restart. Please enter a different address for another district.')        
        window.close()
        main()
           


#webscrape for representative first and last name
#create a dictionary or end range based on district number?
def repLastName(disno):   
    numofdistricts = 203
    repres = requests.get('https://www.legis.state.pa.us/cfdocs/legis/home/member_information/mbrList.cfm?body=H&sort=district')
    soup = BeautifulSoup(repres.content, 'html.parser')
    MemberDirectory = soup.find(id)
    MemberList = MemberDirectory.find(class_ = 'MemberInfoList-ListContainer clearfix')
    
    #create a representative directory; key is district number, value is member's name
    repNamedict = {}   
    for i in range(1, numofdistricts+1):    
        NextMember = MemberList.find_next(class_ = 'MemberInfoList-MemberWrapper')
        IndMember = NextMember.find(class_ = 'MemberInfoList-MemberBio')
        FullName = IndMember.find_next('a')
        MemberList = NextMember
        repNamedict[str(i)] = FullName.text.rstrip()
    #extract the representative of interest (by district number key)
    repName = repNamedict[disno]
    
    #get just the last name of the representative
    namepattern = r'^(.+?),'
    repLast = re.search(namepattern,repName).group()
    
    return repLast[:-1]


def egap():
    
    house_districts = pd.read_csv(r'house_candidate.csv')
    # Convert the house_candidate.csv into a pandas dataframe
    
    connection = sqlite3.connect('electiondb.sqlite')
    # create and connect to the electiondb.sqlite database
    
    try:
        house_districts.to_sql(name='house_districts', con=connection)
        # import the house_districts dataframe into the created database
    except:
        test = "DB Already Created"
    
    query = """
    SELECT SUM(s.sum)
    FROM (SELECT SUM(total_votes) as sum
          FROM house_districts
          WHERE district LIKE 'Pennsylvania%'
          GROUP BY district) s;
    """

    cursor = connection.cursor()

    cursor.execute(query)

    state_total = cursor.fetchall()

    penn_state_total = state_total[0][0]
    # Calculating the total number of votes cast in Pennsylvania
    
    query = """
    SELECT pd.district, pd.total_votes - pr.total_votes AS vote_difference, 
        CASE
            WHEN pd.total_votes - pr.total_votes < 0 THEN
                pd.total_votes
            ELSE
                0
            END dem_lost_votes,
        CASE
            WHEN pd.total_votes - pr.total_votes > 0 THEN
                pr.total_votes
            ELSE
                0
            END rep_lost_votes,
        CASE
            WHEN pd.total_votes - pr.total_votes > 0 THEN
                (pd.total_votes - pr.total_votes) * 0.5
            ELSE
                0
            END dem_surplus_votes,
        CASE
            WHEN pd.total_votes - pr.total_votes < 0 THEN
                abs(pd.total_votes - pr.total_votes) * 0.5
            ELSE
                0
            END rep_surplus_votes
    FROM (SELECT *
          FROM house_districts
          WHERE party = 'DEM' AND district LIKE 'Penn%') pd
            JOIN
         (SELECT *
          FROM house_districts
          WHERE party = 'REP' AND district LIKE 'Penn%') pr
            ON pd.district = pr.district;
    """
    
    cursor = connection.cursor()
    
    cursor.execute(query)
    
    penn1 = cursor.fetchall()
    
    penn_surplost_df = pd.DataFrame(penn1, columns=['District', 'Vote_Difference', 
                                                   'Dem_Lost_Votes', 'Rep_Lost_Votes',
                                                   'Dem_Surplus_Votes', 'Rep_Surplus_Votes'])
    # Calculating the total vote difference along with the lost and surplus votes for each party
    
    try:
        penn_surplost_df.to_sql(name='penn_wasted_votes', con=connection)
        #Creating another table in the database with the penn_surplost_df dataframe
        
    except:
        test2 = "DB Already Created 2"    
    
    query = """
    SELECT sum(x.dem), sum(x.rep), sum(x.dem) - sum(x.rep)
    FROM (SELECT district, dem_lost_votes + dem_surplus_votes as dem, 
                     rep_lost_votes + rep_surplus_votes as rep
          FROM penn_wasted_votes) x;
    """
    
    cursor = connection.cursor()
    
    cursor.execute(query)
    
    penn3 = cursor.fetchall()
    
    penn_wasted_total = pd.DataFrame(penn3, columns=['Dem Total', 'Rep Total', 'Difference In Totals'])
    
    penn_gap = (penn_wasted_total.loc[0]['Difference In Totals'])/penn_state_total

    return str('The state of Pennsylvania has a {:.2f}% efficiency gap'.format(abs(penn_gap)*100))



def popRank():
    
    # use API to get population by each state legislative district
    url= 'https://api.census.gov/data/2014/acs/acs5?get=B01003_001E&for=state%20legislative%20district%20(lower%20chamber):*&in=state:42'
    response = requests.get(url)
    if response.status_code== 200:
        data = json.loads(response.content.decode('utf-8'))
    
    
    # create a data frame with API data
    popData = pd.DataFrame(data[1:], columns=data[0])
    fips_added = popData['state'] + popData['state legislative district (lower chamber)']
    popData['fips'] = fips_added
    #fipsdf = popData
       
    
    # clean up df
    #fipsdf = fipsdf.rename(columns={"state legislative district (lower chamber)": "Pennsylvania House of Representatives District", "B01003_001E": "Population"})
    #print(fipsdf)
    #fipsdf = fipsdf.set_index("Pennsylvania House of Representatives District")
    popData.drop(columns=['state'],inplace=True)
    popData.drop(columns=['fips'],inplace=True)
    popData = popData.rename(columns={"state legislative district (lower chamber)": "Pennsylvania House of Representatives District", "B01003_001E": "Population"})
    #popData = popData.set_index("Pennsylvania House of Representatives District")
     
    # create column with difference from average population and percent
    popData["Population"] = pd.to_numeric(popData["Population"])
    popPA = popData['Population'].sum()
    avgPop = int(popPA/len(popData['Population']))
    
    #calculate percent difference between average population and actual 
    #population for each district
    popDif = []
    percentDif = []
    for value in popData["Population"]:
        x = abs(value-avgPop)
        popDif.append(x)
        y = round((x/avgPop)*100, 2)
        percentDif.append(y) 
       
    popData['Population Difference'] = popDif
    popData['Percent Difference'] = percentDif
    
    #rank districts by by percent difference from average population
    popData['Rank'] = popData['Percent Difference'].rank(method = 'dense')
    sortpopData = popData.sort_values(by= 'Rank')
    
    return sortpopData


#call script generator
#Only runs if user's district is ranked high for gerrymandering
def callScript(userFName,userLName, disno):
    #sample inputs
    #can run this section through first print to get the call script
    repName = repLastName(disno)
    popinfo = popRank()
    
    if len(disno) < 3:
        disno = "0" + disno 
    
    #get the rank and percent difference that corresponds to the given district number
    popdis = popinfo['Pennsylvania House of Representatives District'] == disno
    rank = int(popinfo.loc[popdis, 'Rank'].values)
    percentDiff = float(popinfo.loc[popdis, 'Percent Difference'].values)
    
    #get Pennsylvania's overall efficiency wage gap        
    effwagerank = egap()
    
    #run choromap function to generate map
    choromap()
    
    #generate call script
    opener = 'Hello Honorable {}'.format(repName)
    body = re.sub('\s+', ' ', ('''My name is {} {} and I am a resident of
                  District {}. As your constituent, I am calling to
                  express my concern about the level of gerrymandering in 
                  our district. {}, and we rank {}th in the state out of 203 
                  districts with a population percent difference of {}% in 
                  how equally weighted our votes are to other voters statewide. 
                  These numbers suggest that we have a lot of wasted votes 
                  in our district. I urge you to address these unjust acts 
                  that steal your constituents of their right to a free and 
                  fair election. I appreciate your time and commend you 
                  for the continued dedication that you have in supporting 
                  and protecting the rights of us, your community.'''.format(
                  userFName,userLName,disno, effwagerank, rank, percentDiff)))
    
    return opener +'\n'+ body

def choromap():
    try:
        from osgeo import ogr
        driver = ogr.GetDriverByName('ESRI Shapefile')
        shp_path = r'cb_2014_42_sldl_500k.shp'
        data_source = driver.Open(shp_path, 0)
        
        fc = {
            'type': 'FeatureCollection',
            'features': []
            }
        
        lyr = data_source.GetLayer(0)
        for feature in lyr:    
            fc['features'].append(feature.ExportToJson(as_object=True))
        
        
        
        df = popRank()
        newdf = df.reset_index()
        
        values = newdf['Percent Difference'].tolist()
        
        colorscale = [
            'rgb(234,90,97)',
            'rgb(154,46,127)',
            'rgb(97,25,125)',
            'rgb(44,15,87)',
            'rgb(255,255,255)'
        ]
        
        
        
        fig = px.choropleth(newdf, geojson=fc, locations="Pennsylvania House of Representatives District", 
                            color=values, featureidkey="properties.SLDLST",
                            projection="mercator", color_continuous_scale= colorscale)
        
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        fig.show(block=False)
        return plot(fig)
    except Exception:
        sg.PopupError('An error occurred while generating your map. It will not be downloaded to your computer!')
        pass

def PAzipcodes():
    zipDirectory = requests.get('https://www.zipdatamaps.com/list-of-zip-codes-in-pennsylvania.php')
    soup = BeautifulSoup(zipDirectory.content, 'html.parser')
    
    #extracts the zipcode table and converts it to text
    zipRun = soup.find(class_ = 'table table-striped table-bordered table-hover table-condensed')
    zipRun = zipRun.text
    
    #extracts all of the zip code numbers
    alphaZips = re.findall(r'[^"]\d{5}[^"]', zipRun)
    
    #strips the leading and tail alpha characters and creates a new list
    zipList = [code[1:-1] for code in alphaZips]
    
    return zipList


#GUI 
#sets the theme for the GUI      
sg.theme('Topanga')

#initiatizes GUI and runs entire program
def main():
   #defines the layout of the GUI including buttons 
   layout = [[sg.Text("Let's End Gerrymandering Together!\n\n", 
            justification='center')],  
            [sg.Text('\nEnter your First Name:'), sg.InputText()],
            [sg.Text('\nEnter your Last Name:'), sg.InputText()],
            [sg.Text('\nEnter your street address:'), sg.InputText()],
            [sg.Text('\nEnter your city:'), sg.InputText()],
            [sg.Text('\nEnter “PA”:'), sg.InputText()],
            [sg.Text('\nSelect your zipcode:'), sg.Combo(PAzipcodes(), size = (20,4), enable_events = False)],
            [sg.Text('\nPlease select the Gerrymandering Folder as the Destination: ')],
              [sg.In(key='input')],
              [sg.FolderBrowse(target='input')],
              [sg.Text()],
              [sg.Button('Enter'), sg.Exit()]]
    
   #defines the window using the layout
   window = sg.Window("The Gerrymandering Project", layout)
    
   #creates an infinite loop for the GUI to stay open and the code to run
   while True:
       #reads the buttons and entries in the window as events with values
       event, values = window.read() 
       #enables users to close the gui and end the program
       if event is None or event == 'Exit':
           break
       
       try:
           #enables and requires  the user to set the directory
           os.chdir(values['input']) #change the directory to the selected path
       except OSError:
           sg.PopupError('Enter valid download directory')
      
       else:
           #defines what sort of entries are allowed   
           if values[0] == False or values[1] == False or values[2] == False or values[3] == False or values[4] == False or values[5] == False: 
               sg.PopupError('Error! Please Provide A Valid Name and Address!')
           elif values[0] == values[0] and values[0] and values[0][-1] in ('0123456789'): 
               sg.PopupError('Error! Please Provide A Valid First Name!')
           elif values[0] == '': 
               sg.PopupError('Error! Please Provide A Valid First Name!')
           elif values[1] == values[1] and values[1] and values[1][-1] in ('0123456789'): 
               sg.PopupError('Error! Please Provide A Valid Last Name!')
           elif values[1] == '':
               sg.PopupError('Error! Please Provide A Valid Last Name!')
           elif values[2] == '': 
               sg.PopupError('Error! Please Provide A Valid Street Address!')
           elif values[3] == values[3] and values[3] and values[3][-1] in ('0123456789'): 
               sg.PopupError('Error! Please Provide A Valid City!')
           elif values[3] == '': 
               sg.PopupError('Error! Please Provide A Valid City!')
           elif values[4] == values[4] and values[4] and values[4][-1] in ('0123456789'): 
               sg.PopupError('Error! Please Provide A Valid State!')
           elif values[4] == '': 
               sg.PopupError('Error! Please Provide A Valid State!')
           elif values[5] not in PAzipcodes(): 
               sg.PopupError('Error! Please Provide A Valid Zipcode!')
           elif values[5] == '': 
               sg.PopupError('Error! Please Provide A Valid Zipcode!')
           
           else: 
               #defines event enter and runs the remainder of the program
               if event == 'Enter':
                   try:
                       #runs the previously defined functions
                       disno = district_finder(values[2],values[3],values[4], values[5])
                       script = callScript(values[0],values[1], disno)

                       if len(script) > 0:
                            number = repPhone(disno)
                            #creates a file for the call script  
                            if path.exists(script + 'EndGerrymanderingCallScript.txt') == False:
                                f = open("EndGerrymanderingCallScript", "w")
                                f.write(number)
                                f.write('\n')
                                f.write(script)
                                f.close()
                               
                                break
                                   
                            elif path.exists(script + 'EndGerrymanderingCallScript.txt') == True:
                                sg.PopupError('File path already exists! Enter different name and address...')
                            else:
                                if values[0] == False or values[1] == False or values[2] == False or values[3] == False or values[4] == False or values[5] == False: 
                                    sg.PopupError('Error! Please Provide A Valid Name and Address!')
                       else:
                            sg.PopupError('Python is Restarting!')
                            window.close()
                            main()  

               
                   except Exception:
                       sg.PopupError('Python is Restarting!')
                       window.close()
                       main()
   window.close()                

#runs entire program
if __name__ == '__main__':
    main()
                 



