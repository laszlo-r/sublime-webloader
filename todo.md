
BEFORE PUSHING:
---------------
+ verify license
+ remove debug messages or flags
+ update website, remove php
- update linkedin: activity + projects, remove php

TODO:
-----
+ file urls can be urlencoded, also test file:/// mode; seems to work with (ascii) escaped urls
+ implement clients setting; set ip limit on clients to prevent flooding/hacks
+ implement save_parsed_less: find the less file in client.files; save the parsed content beside it as .css; has to be enabled in settings!
+ complete js command: quick panel if multiple clients, send to selected (or current) client
+ server command: start/stop/restart; also sends 'cmd file multi line content' to all clients
+ implement sites setting; work with the examples listed in the settings file
+ when changing settings, plugin should notice, and clients should update their patterns; implemented for important settings
+ webloader.js runs on dom:loaded, can be put anywhere on the page
+ converting less: less parser now gets a rootpath (prefixes url()), which is the relative path between the page and the less file
- update readme
- test utf8 characters in urls and paths, test linux paths (currently first bit removed with paths like file:///C:/)
- test various sites settings, virthosts, symlinked paths, etc
- hotkey for page reload for the selected/single client; definitely, page reloading on every save may be annoying and slow for some
- add menu items for options and commands
- currently clients can call self.server, which could have exited and been deleted meanwhile
- submit to package control <http://wbond.net/sublime_packages/package_control/package_developers>
- revisit and test bigger css updates, like whole less blocks, fix selector updates (not updated on edit, only with saving)
  - faster updates: could only send the current key-value pair, between previous and next semicolons or brackets, maybe validate them
  - multiple selections: with less you probably factor out frequently used values into variables, so not a priority
  - a full refresh would be is necessary, which is slow with large files + typing; could timeout for 0.5-1sec when multiple selections
- lesscss is apache 2 licensed (free, include all credits), prototype is MIT (free)

Matching
--------

	except for the index page, we can't know what the project's dir is, but if we find the common part (if any)
	in page and reference urls, we can match html and php (or any type) files to that
		current page: */ or */some/page
		linked file:  */media/some.css
		other linked: */js/some.js
		if localhost: * + file paths -> /basepath/some/page(page|filepath)
		if virthost:  /virthost.com* + file paths -> /virthost.com/basepath/(page|filepath)

	"sites", aka user-defined pathname -> url combinations, if either:
		- different directory name and virthost
		- user-friendly urls, redirects, hiding direct .php and .html access
		- folders/files symlinked to docroot, but editing files in the original location
		- various templates which obviously won't match directly to urls

			/www/mywebdir/projectname/* -> customvirthost:8080/*
			/totally/different/folder/* -> domain.com/website/subpages/*

What should match by default:
-----------------------------

	localhost:
		for referenced file types:
			/www/project/rootfile.css					/project/rootfile.css
			/www/project/some/file.css					/project/some/file.css
		file is a "template", and the path matches a page url:
			/www/project/index.(html|php)				/project/(index.(html|php))
			/www/project/some/other.(html|php)			/project/some/other.(html|php)
	virthost:
		path ends with the domain + url:
			/www/project.com/rootfile.css				project.com + /rootfile.css
			/www/project.com/some/file.css				project.com + /some/file.css
		file is a "template", and the path matches a domain + page url:
			/www/project.com/index.(html|php)			project.com + /(index.(html|php))
			/www/project.com/some/other.(html|php)		project.com + /some/other.(html|php)

	if "*" is allowed, try:
		path ends with the url:
			*/project/some/file.css -> /project/some/file.css
			*/rootfile.css  -> */rootfile.css
			*/some/file.css -> */some/file.css
		file is a "template", and the path matches a domain + page url:
			*/index.(html|php)      -> */(index.(html|php))
			*/some/other.(html|php) -> */some/other.(html|php)

