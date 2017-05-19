# -*- coding: utf-8 -*-
from __future__ import print_function
from scrapy import Spider, Request, FormRequest
import json
import os


class LinkedinSpider(Spider):
    name = "linkedin"
    allowed_domains = ["linkedin.com"]

    def start_requests(self):
        # we start by requesting the landing page
        return [Request(
            "https://www.linkedin.com",
            callback=self.do_login
        )]

    def do_login(self, response):
        # we use the form from the landing page (with CSRF and stuff)
        # to login properly
        jsessionid = self.get_cookie(response, 'JSESSIONID')
        request = FormRequest.from_response(
            response,
            formdata={
                'session_key': os.environ['LINKEDIN_USER'],
                'session_password': os.environ['LINKEDIN_PASSWORD']
            },
            callback=self.get_search_page
        )
        request.meta['jsessionid'] = jsessionid
        yield request

    def get_search_page(self, response):
        # not much to do with the response here since it's all JS frontend crap
        # but at this point we should have the cookies to be logged in
        # so we can fire the search
        #
        # this function will call itself incrementing the page number

        start = response.meta.get('start')

        if start is None:
            start = 0

        if start > 10:
            jsonresponse = json.loads(response.body_as_unicode())
            if len(jsonresponse["elements"]) == 0:
                yield None
                return

        request = Request(
            "https://www.linkedin.com/voyager/api/search/"
            "cluster?count=10&guides=List()&keywords=HR"
            "&origin=GLOBAL_SEARCH_HEADER&q=guided&start=%s" % (start,),
            headers={"Csrf-Token": response.meta['jsessionid']},
            callback=self.get_search_page
        )
        request.meta['start'] = start + 10
        request.meta['jsessionid'] = response.meta['jsessionid']
        yield request

        infokey = "com.linkedin.voyager.search.SearchProfile"
        pi = "publicIdentifier"

        if start > 10:
            jsonresponse = json.loads(response.body_as_unicode())
            for p in jsonresponse["elements"]:
                for pp in p["elements"]:
                    publicidentifier = \
                        pp["hitInfo"][infokey]["miniProfile"][pi]
                    if publicidentifier != "UNKNOWN":
                        info = Request(
                            "https://www.linkedin.com/voyager"
                            "/api/identity/profiles"
                            "/%s/profileContactInfo" %
                            (publicidentifier.encode('utf-8'), ),
                            headers={
                                "Csrf-Token": response.meta['jsessionid']
                            },
                            callback=self.get_personal_data
                        )
                        info.meta['public_identifier'] = \
                            publicidentifier.encode('utf-8')
                        yield info

    def get_personal_data(self, response):
        jsonresponse = json.loads(response.body_as_unicode())
        twitter_handle = None
        publicidentifier = response.meta.get('public_identifier')

        included = jsonresponse.get("included")
        if included:
            for i in included:
                if i.get("$type") == \
                        "com.linkedin.voyager.identity.shared.TwitterHandle":
                    twitter_handle = i.get("name")

        if twitter_handle is None:
            for tw in jsonresponse['twitterHandles']:
                twitter_handle = tw['name']

        if twitter_handle is not None:
            print (
                "https://www.linkedin.com/voyager"
                "/api/identity/profiles"
                "/%s/profileContactInfo" %
                (publicidentifier,), end=",")
            print (twitter_handle)

    def get_cookie(self, response, name):
        for cookie in response.headers.getlist('Set-Cookie'):
            c = cookie.split(';')[0].split('=')
            if c[0] == name:
                return c[1].replace('"', '')
