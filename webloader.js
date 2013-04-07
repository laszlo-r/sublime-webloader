(function(window) {

function WebLoader() {

	this.init = function() {
		// console.clear();
		this.debug = 1;

		this.collect_files();
		this.setup_commands();
		this.setup_callbacks();

		this.connect();
	}

	this.collect_files = function() {
		// regexps for extracting the path+filename and the optional server=... definition from an url
		var domain = "(?:https?:)?//[\\w\\.-]+", 
			path = "(/.+\\.(?:less|css|js))", 
			params = "\\?(?:[\\w&:=_-]*&)*", 
			server_param = "server=([\\w\\.-]+)?(?::([0-9]{3,})?)?(/[\\w/_-]*)?", 
			ending = "(?:&|$)?", 
			pattern = domain + path + "(?:" + params + server_param + ending + ")?"

		this.file_pattern = RegExp(pattern)
		// this.test_regexp(this.file_pattern, 5); // pattern, expected number of pieces

		var get_file_info = function(a) { return (a = a.href || a.src) && (a = a.match(this)) && a.slice(1); }, 
			files = document.head.childElements().map(get_file_info, this.file_pattern).filter(this.self);

		this.check_server_params(files);

		this.files = files.map(function(a) { return a[0]; });
	}

	this.check_server_params = function(files) {
		var server = { host: 'localhost', port: 9000, url: '/file_updates' }, 
			server_params = ['host', 'port', 'url'], 
			scriptname = '/webloader.js';
		server.url = '';

		var param_name = function(x, i) { return x && [server_params[i], x]; }, 
			get_params = function(a) { return a && a[0] && a[0].endsWith(scriptname) && a.slice(1).map(param_name).without(undefined); }, 
			add_params = function(a) { if (a && a[1]) this[a[0]] = a[1]; };

		(files.map(get_params).without(0).first() || []).each(add_params, server);
		this.server = server;
	}

	this.request_watching = function() {
		if (this.debug > 1) this.log('watching ' + this.files.join(', '));
		else this.log('watching ' + this.files.map(function(a) { return a.slice(a.lastIndexOf('/') + 1); }).join(', '));
		this.socket.send('watch\n' + this.files.join('\n'))
	}

	// file can be an element with href or src, or a file handle from this.files (even a partial match)
	// returns the basepath + filename + extension like this:
	// "http://domain.com/some/path/this.file?with=params" -> "/some/path/this.file"
	this.file_handle = function(file) {
		if (typeof file !== 'string') file = file.href || file.src;
		if (file.indexOf('//') > -1) return (file = file.match(this.file_pattern)) && file[1] || '';
		return this.files.filter(function(a) { return a.endsWith(file); }).first() || ''
	}

	this.file_element = function(filehandle) {
		if (!filehandle.startsWith('/')) filehandle = this.file_handle(filehandle)
		var matches = function(a) { return (a.href || a.src || '').split('?')[0].endsWith(filehandle); };
		return document.head.childElements().filter(matches).first();
	}

	this.parse_command = function(message) {
		if (this.debug > 2) this.log(message)

		var tmp = message.data.split('\n', 2), 
			cmd = tmp[0], 
			file = (tmp[1] || '').strip(), 
			content = tmp[1] === undefined ? '' : message.data.slice(tmp[0].length + tmp[1].length + 2), 
			single_arg = cmd.length && cmd.indexOf('"') > -1 && cmd.indexOf(' ');

		// examine the command line:
		// false: no '"' -- split by spaces
		// 0 (no length) or -1 (no space) -- single array
		// else: split by first space, let the command method sort out arguments

		cmd = single_arg === false ? 
			cmd.split(' ').without('') :
			(single_arg <= 0 ? [cmd] : [cmd.slice(0, single_arg), cmd.slice(single_arg + 1)])

		this.command(cmd, file, content, message);
	}

	this.command = function(cmd, file, content, message) {
		var item = file && typeof file === 'string' ? this.file_element(file) : file;
		if (typeof cmd === 'string') cmd = [cmd];

		return this.commands[cmd[0]] ?
			this.commands[cmd[0]].apply(this, [cmd, item, content]) : 
			this.debug && this.log(
				'unknown command "%s"\n-- file: "%s"\n-- content (%s):\n%s-- message:', 
				cmd.join(' '), file, content.length, content.replace('\n', '\\n\n') + (content.endsWith('\n') ? '' : '\n'), message);
	}

	this.add_command = function(cmd, f) { this.commands[cmd] = f; }

	this.setup_commands = function() {
		this.commands = {}

		this.add_command('message', function(cmd, file, content) {
			this.log(content);
		})

		this.add_command('reload_page', function(cmd, file, content) {
			window.location.reload();
		})

		this.add_command('reload_file', function(cmd, file, content) {
			if (!file.href && !file.src) return this.log('cannot find the element of "%s"', file)

			var clone = function(a) {
				var e = document.createElement(a.tagName), attr = (a.href ? 'href' : 'src');
				$A(a.attributes).each(function(x, i) { e[x.name] = x.value; });
				e.className += (e.className ? ' ' : '') + 'reloaded:' + this.stime();
				e[attr] = e[attr] + (e[attr].indexOf('?') > -1 ? '&' : '?') + this.stime();
				return e;
			}

			var twin = clone.apply(this, [file]);
			this.log('reloading %s %s (%s)', twin.tagName.toLowerCase(), twin.href || twin.src, cmd[1] || 'no reason');
			file.parentNode.replaceChild(twin, file);
			this.onreload(twin, cmd);
		})

		var reload_file = function(cmd, file, content) {
			this.command(['reload_file', 'was ' + cmd[0]], file)
		}

		this.add_command('opened', reload_file);
		this.add_command('saved', reload_file);
		this.add_command('closed', reload_file);

		this.add_command('update', function(cmd, file, content) {
			if (file.type === 'text/css' && content) this.less_update(file, content);
			else console.log(cmd, file, content);
		})

		this.add_command('run', function(cmd, file, content) {
			if (content && content.length) console.log(eval(content))
		})
	}

	this.setup_callbacks = function() {
		this.onreloads = {
			'*': function(item, file, cmd) {
				var len = this.stime().length, attr = item.href ? 'href' : 'src', url = item[attr];
				if (url.slice(-len).match(/[0-9]{2}:[0-9]{2}:[0-9]{2}$/)) {
					if (this.debug > 1)
						this.log('removing hash from url: %s', url);
					len = -len - (url.slice(-len - 1, -len) === '?' || url.slice(-len - 1, -len) === '&' ? 1 : 0);
					item[attr] = url.slice(0, len);
				}
			}, 
			less: function(item, file, cmd) {
				// this.log('reloaded less file:', item);
				var ref = this, style = item.nextSibling, url = item.href;

				// if neither a .less extension, nor a less declaration, ignore it
				if (!((item.rel && item.rel === 'stylesheet/less') || file.slice(file.lastIndexOf('.') + 1) === 'less'))
					return
				// use the less-generated style element for updating
				if (!style.id || (!style.id.startsWith('less:') && !style.id.startsWith('less-webloader:')))
					return this.log('when updating %s, found this style:', file, style);

				this.remove_custom_styles(file);

				new Ajax.Request(url, {
					onFailure: function(response) {
						ref.log('could not refresh %s!', url);
					}, 
					onSuccess: function(response) {
						if (this.debug > 1)
							ref.log('ajax: updating %s with %s', url, response.responseText)
						style.textContent = ref.less_parse(response.responseText);
					}
				});
			}
		}
		this.onreloads.css = this.onreloads.less;

		this.onupdates = {
		}
	}

	this.call_event = function(event, item, cmd) {
		var file = this.file_handle(item), ext = file.split('.').pop();
		if (this.debug > 1)
			this.log('on%s %s:', event, item.tagName.toLowerCase(), item);
		event = 'on' + event + 's';
		this[event]['*'].apply(this, [item, file, cmd]);
		return this[event][ext] && this[event][ext].apply(this, [item, file, cmd]);
	}

	this.onreload = function(item, cmd) { return this.call_event('reload', item, cmd); }
	this.onupdate = function(item, cmd) { return this.call_event('update', item, cmd); }


	/// less and css-related stuff

	this.less_handle = function(file) {
		return (file = this.file_handle(file)) && 'less:' + file.replace(/[^\w\.-]+/g, '-').slice(1, file.lastIndexOf('.'));
	}

	this.custom_less_handle = function(file, id) {
		return this.format('less-webloader:%s:%s', file, (id ? id.replace(/ /g, '-') : ''));
	}

	this.less_element = function(file) {
		var handle = this.less_handle(file);
		return $A(document.getElementsByTagName('style')).filter(function(a) { return a.id.startsWith(handle); }).first();
	}

	this.custom_styles = function(file, id) {
		var handle = this.custom_less_handle(file, id);
		return $A(document.getElementsByTagName('style')).filter(function(a) { return a.id.startsWith(handle); });
	}

	this.remove_custom_styles = function(file, id) {
		if (this.debug > 1)
			this.log('removing custom styles for "%s"', this.custom_less_handle(file, id));

		// remove every style for this file, if id not specified
		var styles = this.custom_styles(file, id);
		if (!id) return styles.each(function(a) { a.parentNode.removeChild(a); }).length

		// in every custom style for this file, remove definitions for only that id

		var start = id + ' {\n', ending = "}\n";
		var has_this_id = function(a) { return a.textContent.indexOf('\n' + id) > -1 || a.textContent.slice(0, id.length) === id; }
		var cut_content = function(target) {
			var i = target.textContent.indexOf(start), 
				j = target.textContent.indexOf(ending, i);
			// console.log(('removing "' + start + '...' + ending + '" from ' + target.id).replace(/\n/g, '|'))
			target.textContent = target.textContent.slice(0, i) + target.textContent.slice(j);
		}
		styles.filter(has_this_id).each(cut_content)
	}

	this.less_update = function(file, styles) {
		var handle = this.file_handle(file), 
			sheet = this.less_element(handle),
			id = styles.slice(0, styles.indexOf('{')).strip(), // css selector part
			css, next

		this.remove_custom_styles(handle, id);

		id = this.custom_less_handle(handle, id);
		styles = this.less_parse(styles);

		if (this.debug > 1) 
			this.log('updating "%s", style id "%s", with:\n%s', handle.slice(handle.lastIndexOf('/') + 1), id, styles)

		// lookup or make a style element, put after the "less:" element
		if (!(css = document.getElementById(id))) {
			css = document.createElement('style');
			css.type = 'text/css';
			css.id = id;
			next = (next = file.nextSibling) && next.id && next.id.startsWith('less:') ? next.nextSibling : next;
			file.parentNode.insertBefore(css, next);
		}

		if (css.styleSheet) { // IE
			try {
				css.styleSheet.cssText = styles;
			} catch (e) {
				throw new(Error)("Couldn't reassign styleSheet.cssText.");
			}
		} else {
			(function (node) {
				if (!css.childNodes.length) css.appendChild(node);
				else if (css.firstChild.nodeValue !== node.nodeValue) css.replaceChild(node, css.firstChild);
			})(document.createTextNode(styles));
		}
	}

	this.less_parse = function(styles) {
		if (!less || !less.Parser) return this.log('no less object found, is a less.js included?');
		var err, result
		(new less.Parser).parse(styles, function(err, tree) { result = [err, tree]; });
		return (err = result[0]) ? 
			this.log('less parser: ' + err.message + ' (column ' + err.index + ')') : 
			result[1].toCSS();
	}



	/// websocket stuff

	this.connect = function() {
		var url = "ws://" + this.server.host + ':' + this.server.port + this.server.url + '?client=' + window.location.href;

		this.log('connecting to ' + url.split('?')[0]);
		var ref = this, socket = this.socket = new WebSocket(url); 

		var methods = [
			function onopen() { this.request_watching(); },
			function onclose() { this.log('websocket closed'); },
			function onmessage(message) { this.parse_command(message); }
		]

		methods.each(function(func) { socket[func.name] = function() { func.apply(ref, arguments); } });

		return this.socket;
	}

	this.reconnect = function(server) {
		if (server) this.server = server;
		return (this.socket && this.socket.close()) || this.connect();
	}



	/// utilities

	this.hash = function(str) {
		var hash = 0, letter;
		if (str.length === 0) return hash;
		for (i = 0; i < str.length; i++) {
			letter = str.charCodeAt(i);
			hash = ((hash<<5) - hash) + letter;
			hash = hash & hash; // Convert to 32bit integer
		}
		return hash;
	}

	this.stime = function() { return (new Date()).toTimeString().slice(0, 8); }

	this.log = function() {
		if (!this.debug || !arguments.length) return;

		// add a prefix, attached to the first argument if it's a string
		var prefix = '[webloader ' + this.stime() + '] ',
			add = (typeof arguments[0] === 'string' ? 1 : 0)
			args = [prefix + (add ? arguments[0] : '')].concat(Array.prototype.slice.call(arguments, add));
		return console.log.apply(console, args);

		// for non-console logging
		// return this.somemethod(this.format.apply(this, args));
	}

	// for non-console messages, something like this could be used in the same format as console.log
	// TODO: add proper %d, %f, %i, maybe %o
	this.format = function() {
		if (arguments.length < 2) return arguments[0];
		var args = arguments;
		return $A(args[0].split('%s')).reduce(function(res, a, i) {
			// console.log('item ' + i + ': "' + a + '", args[' + i + ']: "' + args[i] + '", current result: "' + res + '"')
			return res + (i ? (args[i] === undefined ? '(?)' : args[i]) : '') + a;
		}, '');
	}

	this.self = function(x) { return x; }

	this.test_regexp = function(file_pattern, expected) {
		var protocols = [
			'http://',
			'https://',
			'//'
		]
		var domains = [
			"localhost", 
			"127.0.0.1", 
			"some.domain.com"
		]
		var paths = [
			'simple/', 
			'some/path/', 
			'some_more-paths/', 
			'some_more-paths/qu%20te/long/-in/fact/', 
			'/'
		]
		var files = [
			'som-e.js',
			'silly_named_.css',
			'A12FU_1a.less'
		]
		var params = [
			'simple=1', 
			'some=more&vars=__3', 
			'some_illegal_too'
		]
		var hosts = ['some-server-host', '']
		var ports = [':9000', ':', '']
		var urls = ['/some_url/path', '/', '']

		var generate = function(list, prefix) {
			return function (a) { return list.map(function(x) { return a + prefix + x; }); };
		}

		// paths get a '/' prefix; query params a '?'; etc

		var result = $A(protocols).
			map(generate(domains, '')).flatten().
			map(generate(paths, '/')).flatten().
			map(generate(files, '')).flatten().
			map(generate(params, '?')).flatten().
			map(generate(hosts, '&server=')).flatten().
			map(generate(ports, '')).flatten().
			map(generate(urls, '')).flatten();

		// return a specific item, if asked
		if (expected < 0) return [result[-expected]];

		var errors = result.filter(function(a) { return (a.match(file_pattern) || []).length !== expected; });

		// console.log(file_pattern)
		// console.log((result[0].match(file_pattern) || []).join('\n'))

		console.log('file pattern test: %s/%s errors%s', errors.length, result.length, 
			(errors.length || '') && ', example: ' + errors[0] + '\n' + (errors[0].match(file_pattern) || []).join('\n'))
		return !errors;
	}

	this.init();
	return this;

}

return window.webloader = new WebLoader();

})(window);
