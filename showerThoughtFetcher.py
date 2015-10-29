#!/usr/bin/python3
import praw


def main():
    shitty_reddit_words = ['Reddit', 'reddit', 'Karma', 'karma', 'Repost', 'repost', 'Vote', 'vote']
    r = praw.Reddit(user_agent='shower thought fetcher')

    submissions = r.get_subreddit('showerthoughts').get_top_from_day(limit=10)

    for entry in submissions:
        if len([word for word in shitty_reddit_words if word in entry.title]) == 0:
            return entry.title

if __name__ == "__main__":
    print(main())
