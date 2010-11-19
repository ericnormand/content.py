=Content.py

==Introduction

Content.py is a Python script for scraping the content from a web page. Most pages are covered in ads, navigation, and other crap. Content.py tries to remove the crap and return a clean, well-formatted div of content.

==Usage

Call `getContentFromURL` and pass it the url (as a string) of any web page.

It will return a unicode string representing the html of the content.
