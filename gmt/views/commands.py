"""Flask commands.

This file contains Flask commands that can be executed from the command line.
At the moment this only contains a command that can be run from a cron job that has been
set up with GitHub Actions.
"""

import datetime
from time import sleep

import arrow
import json
import os
import random
import re

import openai
import requests
from flask import Blueprint, render_template, current_app
from flask_mail import Message
from markdown import markdown

from .. import mail, mongo
from ..news import get_news

bp = Blueprint("commands", __name__)


def get_current_time() -> str:
    """Return the current time.

    The function will round the time to 30 minutes. To ensure the email will be sent
    correctly.
    """
    current_time = arrow.utcnow()
    current_time = current_time.replace(minute=30 if current_time.minute >= 30 else 0)
    current_time = current_time.strftime("%H:%M")
    return current_time


@bp.cli.command()
def send_emails() -> None:
    """Send the emails.

    The function will send the emails containing the rendered template of the daily news
    to every confirmed user in the database.
    """
    current_time = get_current_time()
    print(f"Sending email batch of {current_time} UTC")

    all_users = mongo.db.users.find({"confirmed": True})
    all_users = list(all_users)

    users = []
    for user in all_users:
        local_time = arrow.now(user["timezone"])
        utc_time = local_time.replace(hour=int(user["time"]), minute=0).to("utc")
        utc_time = utc_time.strftime("%H:%M")
        if utc_time == current_time:
            users.append(user)

    print(f"Email will be sent to: {len(users)} User{'s' if len(users)!=1 else ''}")

    configs = {}
    for user in users:
        # if the user has a frequency and the current day is not in the frequency skip the user
        if not datetime.datetime.utcnow().weekday() + 1 in user["frequency"]:
            continue
        # appends all the options into a string and separates news and extras with a '|'
        user_string = ""
        user_string += " ".join(user["news"])
        user_string += "|"
        user_string += " ".join(user["extras"])

        # if the unique config is not already stored add it to the dictionary
        if user_string not in configs:
            configs[user_string] = [user["email"]]
        else:
            configs[user_string].append(user["email"])

    for config, emails in configs.items():
        sources = config.split("|")[0].split(" ")
        extras = config.split("|")[1].split(" ")
        source_amount = len(sources)

        news = mongo.db.articles.find(
            {
                "source": {"$in": sources},
                "date": {
                    "$gte": datetime.datetime.utcnow() - datetime.timedelta(days=1, minutes=30)
                },
            }
        )
        news = list(news)
        random.shuffle(news)
        # news_per_source = int(8 / source_amount)

        # EQUALLY DISTRIBUTE THE NEWS across sources
        if source_amount == 1:
            # Means that there is only one source
            news = news[:8]
        else:
            news_per_source = 8 // source_amount
            remaining_news = 8 % source_amount

            # create a dictionary to store the selected news articles for each source
            source_news = {source: [] for source in sources}

            # iterate over the news articles and add them to the corresponding source_news list
            for article in news:
                source = article["source"]
                if len(source_news[source]) < news_per_source:
                    source_news[source].append(article)
                elif remaining_news > 0:
                    source_news[source].append(article)
                    remaining_news -= 1
                if sum(len(s) for s in source_news.values()) == 8:
                    break

            # flatten the dictionary to a list and shuffle the result
            news = [article for source in source_news.values() for article in source]

        random.shuffle(news)

        html = render_template(
            "general/news.html",
            posts=news,
            markdown=markdown,
            domain_name=current_app.config["DOMAIN_NAME"],
        )
        msg = Message(
            f"Good Morning Tech",
            sender=("Good Morning Tech", current_app.config["MAIL_USERNAME"]),
            bcc=emails,
            html=html,
        )
        mail.send(msg)

    # print(configs)


@bp.cli.command()
def summarize_news():
    """Summarize the news."""
    summarized_news_collection = []
    old_news = mongo.db.articles.find(
        {
            "date": {"$lt": datetime.datetime.utcnow() - datetime.timedelta(hours=25)},
            "source": {"$ne": "GMT"},
        }
    )
    old_news_urls = [news["url"] for news in old_news]
    api_key = current_app.config["SUMMARIZATION_API_KEY"]
    openai.api_key = current_app.config["OPENAI_API_KEY"]
    with open("rss.json") as f:
        rss = json.load(f)
        for key, value in rss.items():
            if key.startswith("_"):
                continue
            raw_news = get_news(key, 16)
            news_amount = 0
            for news in raw_news:
                if (
                    news["url"] in summarized_news_collection
                    or news["url"] in old_news_urls
                ):
                    continue
                elif news_amount >= 8:
                    break

                description = news["description"]

                for link in re.findall(
                    pattern=r"""(?i)\b((?:https?:(?:/{1,3}|[a-z0-9%])|[a-z0-9.\-]+[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)/)(?:[^\s()<>{}\[\]]+|\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\))+(?:\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’])|(?:(?<!@)[a-z0-9]+(?:[.\-][a-z0-9]+)*[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)\b/?(?!@)))""",
                    string=description,
                ):
                    # Replace the link with a Markdown link
                    # description = description.replace(link, f"[link]({link})")
                    description = description.replace(link, "")

                try_count = 0
                while try_count < 3:
                    try:
                        completion = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {
                                    "role": "user",
                                    "content": f"Make the raw text readable as a summary, make sure to retain its length and remove any links and non-sensical text.\nRaw text: '{description}'",  #  Once done, assign it minimum 1 to maximum 3 categories from (Gadget, AI, Robotics, Crypto, Corporation, Gaming, Science, Space, Other) and append it like this Category: category1, category2, category3
                                }
                            ],
                        )
                        if completion["choices"][0]["message"]["content"] == "":
                            raise Exception("No text returned")
                        sleep(20)
                        # finish while loop
                        break
                    except Exception as e:
                        try_count += 1
                        sleep(20)
                        print(f"Failed to summarize news, trying again {e}")
                else:
                    # if all tries failed, skip this news
                    print("Failed to summarize news, skipping")
                    continue

                description = completion["choices"][0]["message"]["content"]

                summarized_news = {
                    "title": news["title"],
                    "description": description,
                    "url": news["url"],
                    "author": news["author"],
                    "thumbnail": news["thumbnail"],
                    "date": datetime.datetime.utcnow(),
                    "source": key.lower(),
                    "formatted_source": key,
                }
                if not summarized_news["title"]:
                    print("Skipped, no title")
                    continue
                summarized_news_collection.append(summarized_news)
                news_amount += 1
                print("summarized")

    if summarized_news_collection:
        # delete all articles that are not from GMT
        mongo.db.articles.delete_many({"source": {"$ne": "gmt"}})

    mongo.db.articles.insert_many(summarized_news_collection)
