from bs4 import BeautifulSoup, NavigableString, Tag
import requests
import re
import datetime

import mysql.connector
import json

mydb = None
TABLE_NAME = "travel_alert"


def connect():
    global mydb

    # populate this from env file
    path_to_json = "./db.json"

    with open(path_to_json, "r") as handler:
        info = json.load(handler)
        print(info)

        mydb = mysql.connector.connect(
            host=info["host"],
            user=info["user"],
            passwd=info["passwd"],
            database=info["database"],
        )

    print(mydb)


def save_to_db():
    connect()
    for alert_object in alert_stack:
        insert(alert_object)


def insert(data_dict):
    table_name = TABLE_NAME
    mycursor = mydb.cursor()
    sql = "INSERT INTO {} (country_name, published_date, added_time, alert_message) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE country_name = %s, published_date = %s, added_time = %s, alert_message = %s".format(
        table_name
    )
    val = (
        data_dict["country_name"],
        data_dict["published_date"],
        data_dict["added_time"],
        data_dict["alert_message"],
        data_dict["country_name"],
        data_dict["published_date"],
        data_dict["added_time"],
        data_dict["alert_message"]
    )
    print("SQL query: ", sql)
    try:
        mycursor.execute(sql, val)
        mydb.commit()
        print(mycursor.rowcount, "record inserted.")
    except Exception as ex:
        print(ex)
        print("Record not inserted")


# Source
url = 'https://www.iatatravelcentre.com/international-travel-document-news/1580226297.htm'
alert_url = requests.get(url, timeout=5)
alert_content = BeautifulSoup(alert_url.content, "html.parser")

nonsense_1 = "If any new travel restrictions will be imposed, we will ensure that Timatic is updated accordingly. We are monitoring this outbreak very closely and we will keep you posted on the developments."

first_filter = alert_content.find_all('body')[1]
entire_string = first_filter.text

countries = []
name_loc = []
alert_stack = []
list_of_lines = []

# Get country name and location in text
for item in first_filter.find_all('strong'):
    country = item.text.strip()
    start = entire_string.find(country)
    end = start + len(country)
    index = (start, end)
    countries.append(country)
    name_loc.append(index)

for br in first_filter.findAll('br'):
    next_s = br.nextSibling
    if not (next_s and isinstance(next_s, NavigableString)):
        continue
    next2_s = next_s.nextSibling
    if next2_s and isinstance(next2_s, Tag) and next2_s.name == 'br':
        text = str(next_s).strip()
        if text:
            list_of_lines.append(next_s)


# Get alert message for each country, which lie between country names except the last one
for country in countries:
    if countries.index(country) < len(countries)-1:
        raw_msg = entire_string[slice(name_loc[countries.index(
            country)][1], name_loc[countries.index(country)+1][0], 1)].strip()

    elif countries.index(country) == len(countries)-1:
        raw_msg = entire_string[slice(name_loc[countries.index(
            country)][1], entire_string.find(nonsense_1), 1)].strip()

    # Get website's update date
    date_string = re.findall(r"[0-9][0-9].[0-9][0-9].[\d]{4}", raw_msg)[0]
    published_date = datetime.datetime.strptime(
        date_string, "%d.%m.%Y").date().strftime("%Y-%m-%d")

    remove_date_msg = raw_msg[slice(raw_msg.find(
        date_string)+len(date_string), len(raw_msg), 1)].strip()

    # Format alert lines for each country:
    # Try to get from list of lines, if missing then patch with entire string for
    # each country.
    country_para = []
    for line in list_of_lines:
        if line in remove_date_msg:
            position_zero_test = remove_date_msg.find(line)

            if not position_zero_test == 0:
                missed_lines = remove_date_msg[slice(0, position_zero_test, 1)]
                country_para.append(missed_lines)
                country_para.append(line)
                list_of_lines = list_of_lines[1:]
                remove_date_msg = remove_date_msg[slice(remove_date_msg.find(
                    line)+len(line), len(remove_date_msg), 1)].strip()

            elif position_zero_test == 0:
                country_para.append(line)
                list_of_lines = list_of_lines[1:]
                remove_date_msg = remove_date_msg[slice(remove_date_msg.find(
                    line)+len(line), len(remove_date_msg), 1)].strip()

    clean_msg = ''.join(x+'|' for x in country_para)+remove_date_msg

    # Timestamp added into database
    added_time = datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    alert_object = {
        "country_name": country,
        "published_date": published_date,
        "added_time": added_time,
        "alert_message": clean_msg

    }

    alert_stack.append(alert_object)


save_to_db()
# print(alert_stack)
