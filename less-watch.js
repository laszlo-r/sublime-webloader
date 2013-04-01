
watch = (function LessWatch(window) {

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
		var url = "ws://" + this.server.host + ':' + this.server.port + this.server.url + '?xclient=' + window.location.href;

		this.log('connecting to ' + url);
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

	this.log = function(message) {
		if (!this.debug) return
		console.log(typeof message === 'string' ? 
			'[less-watch ' + (new Date()).toTimeString().slice(0, 8) + '] ' + message : 
			message
		);
	}

	this.self = function(x) { return x; }

	this.onopen = function() {
		var files = this.files.map(function(a) { return a.replace(/https?:\/\/[\w\.-]+/, ''); });
		this.log('watching ' + files.join(', '));
		this.socket.send('watch\n' + files.join('\n'))
	}

	this.onclose = function() { this.log('websocket closed'); }

	this.onmessage = function(message) {
		this.update(message.data);
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

	this.parse = function(err, tree) {
		this.css = '';
		if (err) return this.log(err.message + ' (column ' + err.index + ')');
		this.css = tree.toCSS();
	}

	this.remove_existing = function(id) {
		id += ' {\n'
		var cut = function(target, from, to, parent) {
			var i = target.textContent.indexOf(from), 
				j = target.textContent.indexOf(to, i)
			// parent.log(('removing "' + from + '...' + to + '" from ' + target.id).replace(/\n/g, '|'))
			return target.textContent.slice(0, i) + target.textContent.slice(j)
		}
		var styles = $A(document.getElementsByTagName('style')).
			filter(function(a) { return a.textContent.indexOf('\n' + id) > -1 || a.textContent.slice(0, id.length) === id; }).
			each(function(a) { a.textContent = cut(a, id, "}\n", this.parent); }, { parent: this })
	}

	this.update = function(styles) {
		var css, id = (styles.slice(0, styles.indexOf('{')).strip());
		var thisref = this, parser = new less.Parser();

		this.remove_existing(id)
		this.log('updating ' + styles)
		parser.parse(styles, function(err, tree) { thisref.parse(err, tree); });

		if (!this.css) return;
		id = 'less-watch:' + id.replace(/ /g, '-')

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

	this.init();

})(window)
