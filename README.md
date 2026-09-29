# Tufts Self-Service App — isolated service rewrite v2


There are many processes that LTFIS has written Python scripts for to support library workflows.  These include getting course data from the Barnes and Noble export, entering 541 gift fund notes from the bib record to the appropriate holding record, and creating gift fund bibliography word docs to send to donors based on titles purchased with their endowed funds that year, among others.  The goal of this app is to create a self service portal where these can all be housed.

This is the replacement for the earlier `tufts-self-service-isolated-rewrite` scaffold.

## Architecture


```
Apache/nginx (unchanged)
        |
        v
127.0.0.1:5002  self-service-gateway
        |
        +-- 5010 main
        +-- 5011 barnes_and_noble
        +-- 5012 bib_2_holdings_541
        +-- 5013 p_and_e_rollup_match
        +-- 5014 gift_fund_bibliography
        +-- 5015 combine_analytics_subjects_areas
        +-- 5016 concurrent_checkouts
        +-- 5017 film_search
```

## Install

```
sudo nano -c /etc/self-service-app/self-service.env   # if it already exists, or run install first to create it
./scripts/install.sh
sudo nano -c /etc/self-service-app/self-service.env
sudo systemctl start self-service.target
./scripts/status.sh
```




## What the parts of this application do


Each of the modules in the self service module, at least those delivered through Flask, were written in Flask/Python A: because Python is a language many people know and use, and B: because many of these modules were based on scripts that existed before the self service module, and some have quite complicated algorithms they use to produce the desired outputs

I will list a high level description of each module that’s in place as of 2026-09-29, how it works, and what high level dependencies it needs.

### Bib 2 Holding 541:
	
This reads a list of locations from an Analtyics report via API, and parses out 541 gift note fields from a list of bib records that are retrieved from the SRU based on an input list file of MMS IDs, and applies this 541 note to the appropriate holdings record, for which it determines location from the analytics report and data in the bib 541

#### Exceptional dependencies:
-	xml.etree.cElementTree
-	pymarc as pym

#### Automated testing:
Since patching occurs every 1st (stage) and 3rd (prod) Sunday of the month, automated testing on this app runs at 6 AM every Sunday.  It uses a local text file of 10 MMS IDs, logs into the 541 module via local login with a stored username and password, and then passes the input file to the /upload endpoint , and emails the results to tulips@tufts.edu.  This is a shell script called test_541.sh that’s invoked by a line in the CRONTAB
### Gift Fund Bibliography:
This is an example of a module that although it sounds like it just outputs Word documents, it does an extraordinary amount of processing to do this, and thus saves a lot of time.  It can take several minutes at least to run as well.
The user supplies the library and fiscal year (format for this in placeholder text as examples) and then retrieves a list of fund expenditures that are considered complete on each of the gift funds for that library via an Analytics fund expenditure report built for this purpose.   Then it takes the MMS ID and does an SRU lookup to receive detailed metadata about each book
Then it uses a local install of citeproc which is basically a Python pseudo-LaTeX processor, which allows you to specific within that dependency directory a CSL stylesheet that can output LaTeX, or in this case BibTex references into specific citation styles, in this case Chicago, because this project was initially requested by Ginn Library, and Fletcher uses Chicago style.
With these citations now properly in Chicago style, which we can be assured of because the raw BibTex (like LaTeX) data was passed to a Chicago stylesheet, it can then be written to a .docx for that fund , that contains all the titles that were purchased with that fund in that fiscal year, so a thank you letter can be sent to donors

#### Exceptional Dependencies:
-	pandas as pd
-	xml.etree.ElementTree as et
-	citeproc_local.py2compat import *
-	services.gift_fund_bibliography.citeproc_local.source.bibtex import BibTeX
-	services.gift_fund_bibliography.citeproc_local import CitationStylesStyle, CitationStylesBibliography
-	services.gift_fund_bibliography.citeproc_local import formatter
-	services.gift_fund_bibliography.citeproc_local import Citation, CitationItem
-	pandas as pd
-	docx


### Enrich Barnes and Noble data with Alma course codes:
This is one of the simpler modules, and it does exactly what the title describes.   It doesn’t really have any special dependenices except normal re for HTTP requests etc.  It just takes a list of readings that are sent to us by Barnes and Noble, the university bookstore, and parses out the course and semester information to get the course code in Alma of each course.  It then passes on the ISBN that is provided, which sometimes isn’t the best one, but Acquisitions and RMRS look these over to assure we are retrieving what is requested to the best of our ability.    
With the output of this module, Acquisitions can feed this into the Overlap Analysis Tool in Alma, for which they have directions, and use it to create a canonical list of MMS IDs and course codes, which are the two things the citation loader Alma cloud app that Henry Steele at LTFIS built uses to create reading lists and their citations.
So this is a simple module, but essential in the reserves and reading list workflow, and allows Acquisitions and reserve departments to create hundreds of reading lists and thousands of citations in days rather than weeks

#### No exceptional dependencies

Combine Analytics Subjects Areas:
This really gets at the heart of the self service purpose of the self service portal.
In Analytics, it is very hard to merge reports from two different subject areas to make a report that merges columns from both based on matching field.  You can either use Analytics Data Visualizations, which frankly is so un-user friendly that Henry as the administrator of Analtyics finds it very difficult to use, or you can create raw SQL for the reports to merge with JOIN…ON
This module takes the latter approach, but allows the user simply paste in the raw XML of two reports they’d like to join, specificy the left on, right on match key, and the kind of join they’d like to do, and then outputs raw SQL that the user can paste into a new report to create the desired output.  This has allowed users who are interested in data analytics and making reports in Analtyics, but aren’t familiar with SQL, and in fact you have to use OBIEE SQL to make this work which is very finicky, to create reports they need in a self-service fashion.   For instance Molly in Tisch Reserves created a whole reserves dashboard in Alma Analytics, with lots of attention to custom prompts, and descriptions that has made reserves stats a lot easier for other reserves stats to use, and in part she used this module to mash up course reserves and physical item data, which exist in two separate Analytics subject areas

#### No exceptional dependencies
	
### Concurrent Checkouts:
This originally a concept that Henry from LTFIS came up with to address the question that Tisch Circ was having on knowing whether they had enough items of high demand , especially tech, like laptops, and what kind of laptops (Mac vs. PC) items to meet the demand of students.  The way it determineded this was to create a matrix of checkout and checkin times in a 2D pandas dataframe and determine how many of those times overlapped at a given time period, and if they number of overlapped periods every reached the total number of items available.  This could then said to have throttled demand if another person had wanted to borrow such an item.
Later for ease of display, the algorithm was simplified to show number of unique items lent on the same day, which isn’t as precise as lent at the same time on the same day, but was much easier to understand in a graph, and is accurate enough for planning purposes.  At the top of the graph is a straight line representing the total number of items.  
#### Exceptional Dependencies:
Although the data structure that it uses to identity collisions or concurrent checkouts, is purpose-built, with items as indices, and unique loan and return dates as columns ordered chronologically, and other dattimes that occur in between those loan and return are marked as “on loan”      it really just uses pandas and numpy

### P and E Rollup Match:
This was a process that was developed for the former head of RMRS to match and rollup physical and electronic titles for collection analysis

It is probably the least used of all these modules now, since it was really bespoke for this head of RMRS, but might be useful in the future if the head of RMRS wanted to use it in their workflow

#### Exceptional Dependencies
-only pandas

### Film Search:
This is the module that most reaches outside of Alma and Tufts resources.   It’s purpose is to take an input workbook of film titles, dates, etc and see if various film publishers’ websites have them for sale.
At the present it looks at 7 publishers websites:
-	Swank
-	Kanopy
-	Alexander Street Press
-	Newday
-	Docuseek
-	Ambrose
-	Criterion
It does a lookup on each website, in some cases choosing academic license as the search filter, and returns results that match the provided metadata
The method for 5 of these , all but Swank and Kanopy, is simple lookup and screen scraping, since the results can be seen in the source HTML, but for Kanopy and Swank, web driving is needed using Selenium because they’re single page applications that don’t expose rendered HTML in the page source.
Because this is looking for static HTML elements, this lookup is somewhat brittle and needs to have regular testing set up for it to ensure accurate results.
#### Exceptional Dependencies
-	selenium
-	Beautiful Soup
