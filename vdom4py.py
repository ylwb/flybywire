# Rename to flybywire
# Write vdom library that produces JSON in format acceptable by
#   vdom-as-json
# Keep leeoniya/domvm in mind
# Make flybywire independent of vdom framework?? Maybe later
#
import asyncio
import os

import json
import webbrowser
import logging

from autobahn.asyncio.websocket import WebSocketServerFactory, WebSocketServerProtocol

class vDom(object):
    def __init__(self):
        self.interface = SofiEventProcessor()
        self.server = SofiEventServer(processor=self.interface)
        self.register('shutdown', self.shutdown)

    @asyncio.coroutine
    def shutdown(self, event):
        logging.info('SHUTDOWN')
        self.server.stop()

    def start(self, autobrowse=True):
        """Start the application"""

        self.server.start(autobrowse)

    def register(self, event, callback, selector=None):
        """Register event callback"""

        self.interface.register(event, callback, selector)

    def unregister(self, event, callback, selector=None):
        """Register event callback"""

        self.interface.unregister(event, callback, selector)

    def load(self, html):
        """Initialize the UI. This will replace the document <html> tag contents with the supplied html."""

        self.interface.dispatch({ 'name': 'init', 'html': html })

    def render(self, vdom):
        """Converts given vdom to JSON and sends it to browser for rendering."""
        
        self.interface.dispatch({ 'name': 'render', 'vdom': json.dumps(vdom)})


class SofiEventProcessor(object):
    """Event handler providing hooks for callback functions"""

    handlers = { 'init': { '_': [] },
                 'load': { '_': [] },
                 'close': { '_': [] },
                 'click': { '_': [] },
                 'mousedown': { '_': [] },
                 'mouseup': { '_': [] },
                 'keydown': { '_': [] },
                 'keyup': { '_': [] },
                 'keypress': { '_': [] },
                 'shutdown': { '_': []},
               }

    def register(self, event, callback, selector=None):
        if event not in self.handlers:
            self.handlers[event] = { '_': [] }

        if selector:
            key = str(id(callback))
        else:
            key = '_'

        if key not in self.handlers[event]:
            self.handlers[event][key] = list()

        self.handlers[event][key].append(callback)

        if event not in ('init', 'load', 'close', 'shutdown') and len(self.handlers[event].keys()) > 1:
            capture = False
            if selector is None:
                selector = 'html'
                capture = True

            self.dispatch({ 'name': 'subscribe', 'event': event, 'selector': selector, 'capture': capture, 'key': str(id(callback)) })

    def unregister(self, event, callback, selector=None):
        if event not in self.handlers:
            return

        if selector is None:
            self.handlers[event]['_'].remove(callback)
        else:
            self.handlers[event].pop(str(id(callback)))

        if event not in ('init', 'load', 'close'):
            self.dispatch({ 'name': 'unsubscribe', 'event': event, 'selector': selector, 'key': str(id(callback)) })

    def dispatch(self, command):
        self.protocol.sendMessage(bytes(json.dumps(command), 'utf-8'), False)

    @asyncio.coroutine
    def process(self, protocol, event):
        self.protocol = protocol
        eventtype = event['event']

        if eventtype in self.handlers:
            # Check for local handler
            if 'key' in event:
                key = event['key']

                if key in self.handlers[eventtype]:
                    for handler in self.handlers[eventtype][key]:
                        if callable(handler):
                            yield from handler(event)

            # Check for global handler
            for handler in self.handlers[eventtype]['_']:
                if callable(handler):
                    yield from handler(event)


class SofiEventProtocol(WebSocketServerProtocol):
    """Websocket event handler which dispatches events to SofiEventProcessor"""

    def onConnect(self, request):
        logging.info("Client connecting: %s" % request.peer)

    def onOpen(self):
        logging.info("WebSocket connection open")

    @asyncio.coroutine
    def onMessage(self, payload, isBinary):
        if isBinary:
            logging.info("Binary message received: {} bytes".format(len(payload)))
        else:
            logging.info("Text message received: {}".format(payload.decode('utf-8')))
            body = json.loads(payload.decode('utf-8'))

            if 'event' in body:
                yield from self.processor.process(self, body)

    def onClose(self, wasClean, code, reason):
        logging.info("WebSocket connection closed: {}".format(reason))



class SofiEventServer(object):
    """Websocket event server"""

    def __init__(self, hostname=u"127.0.0.1", port=9000, processor=None):

        self.hostname = hostname
        self.port = port
        self.processor = processor

        factory = WebSocketServerFactory(u"ws://" + hostname + u":" + str(port))
        protocol = SofiEventProtocol
        protocol.processor = processor
        protocol.app = self

        factory.protocol = protocol

        self.loop = asyncio.get_event_loop()
        self.server = self.loop.create_server(factory, '0.0.0.0', port)

    def stop(self):
        self.loop.stop()

    def start(self, autobrowse=True):
        self.loop.run_until_complete(self.server)

        try:
            path = os.path.dirname(os.path.realpath(__file__))
            if autobrowse:
                webbrowser.open('file:///' + os.path.join(path, 'static/main.html'))
            self.loop.run_forever()

        except KeyboardInterrupt:
            pass

        finally:
            self.server.close()
            self.loop.close()

    def __repr__(self):
        return "<EventServer(%s, %s)>" % (self.hostname, self.port)

    def __str__(self):
        return repr(self)