(function(window) {

function LessWatch() {

	this.init = function() {

		this.server = { host: 'localhost', port: 9000, url: '/less_updates' };
		this.debug = 1

		var file_pattern = /(?:https?:\/\/[\w\.-]+)(\/.+\.less)(?:\?(?:[\w&=_-]*&)*server=([\w\.:_-]+)(?:&|$)?)?/,
			file_info = function(a) { return a.type == 'text/css' && a.href && (a = a.href.match(file_pattern)) && a.slice(1, 3); },
			files = $A(document.getElementsByTagName('link')).map(file_info).filter(this.self), 
			host = (files.map(function(a) { return a[1]; }).filter(this.self).pop() || '').split(':');

		if (host[0]) this.server.host = host[0];
		if (host[1]) this.server.port = host[1];

		this.files = files.map(function(a) { return a[0]; });

		this.connect();
	}

	this.connect = function() {
		var url = "ws://" + this.server.host + ':' + this.server.port + this.server.url + '?client=' + window.location.href;

		this.log('connecting to ' + url.split('?')[0]);
		var socket = this.socket = new WebSocket(url); 
		var ref = this, methods = ['onopen', 'onclose', 'onmessage'];

		methods.each(function(funcname) {
			ref.socket[funcname] = function() { ref[funcname].apply(ref, arguments); }
		});
		return this.socket;
	}

	this.reconnect = function(server) {
		if (server) this.server = server
		return (this.socket && this.socket.close()) || this.connect();
	}

	this.onopen = function() {
		var files = this.files.map(function(a) { return a.replace(/https?:\/\/[\w\.-]+/, ''); });
		this.log('watching ' + files.join(', '));
		this.socket.send('watch\n' + files.join('\n'))
	}

	this.onclose = function() { this.log('websocket closed'); }

	this.onmessage = function(message) {
		if (this.debug > 1) console.log(message)

		message = message.data.split('\n')
		var file = message[0], 
			content = message[1] || '', 
			cmd = content[0] === '/' ? content.slice(1).split(' ') : '';

		switch (cmd[0]) {
			case 'refresh':
				this.log('refreshing ' + file + (cmd[1] ? ' (it was ' + cmd[1] + ')' : ''));
				this.remove_existing(file) && less && less.refresh(1); // refresh has a reload flag
				break;
			case 'message':
				this.log(content.slice(content.indexOf(' ')));
				break;
			default:
				if (content) this.update(file, content);
		}
	}

	this.style_name = function(file, id) { return 'less-watch:' + file + (id ? ':' + id.replace(/ /g, '-') : ''); }

	this.styles_matching = function(file) {
		file = this.style_name(file)
		return $A(document.getElementsByTagName('style')).filter(function(a) { return a.id.startsWith(file); });
	}

	this.remove_existing = function(file, id) {
		var styles = this.styles_matching(file, id);
		if (!id) return styles.each(function(a) { a.parentNode.removeChild(a); }).length

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

	this.update = function(file, styles) {
		var ref = this, parser = new less.Parser(), css, id

		id = styles.slice(0, styles.indexOf('{')).strip(); // css selector part
		this.remove_existing(file, id)

		// prefix + less_file_name + css-selector-part
		// TODO: hashing?
		id = 'less-watch:' + file + id.replace(/ /g, '-')

		if (this.debug > 1)
			this.log('updating ' + file.slice(file.lastIndexOf('/') + 1) + ': ' + styles)
		parser.parse(styles, function(err, tree) { ref.parse(err, tree); });

		if (!this.css) return;

		if ((css = document.getElementById(id)) === null) {
			css = document.createElement('style');
			css.type = 'text/css';
			css.id = id;
			document.getElementsByTagName('head')[0].parentNode.insertBefore(css, null);
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

	this.parse = function(err, tree) {
		this.css = '';
		if (err) return this.log(err.message + ' (column ' + err.index + ')');
		this.css = tree.toCSS();
	}

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

	this.log = function(message) {
		if (!this.debug) return
		console.log(typeof message === 'string' ? 
			'[less-watch ' + (new Date()).toTimeString().slice(0, 8) + '] ' + message : 
			message
		);
	}

	this.self = function(x) { return x; }

	this.init();
	return this;

}

return window.watch = new LessWatch();

})(window);
