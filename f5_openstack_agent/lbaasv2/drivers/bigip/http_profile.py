# -*- coding: utf-8 -*-

class HTTPProfileHelper(object):

    def __init__(self):
        self.insertXforwardedFor = ""

    def set_xff(self, listener):
        xff_enable = self.http_xff_enable(listener)
        if xff_enable:
            self.insertXforwardedFor = "enabled"
        else:
            self.insertXforwardedFor = "disabled"

        return {
            "insertXforwardedFor": self.insertXforwardedFor
        }

    def http_xff_enable(self, listener):
        if listener['protocol'] in ['HTTP', 'TERMINATED_HTTPS']:
            return listener.get('transparent', False)
        return False

    def need_update_xff(self, old_listener, listener):
        if listener['protocol'] in ['HTTP', 'TERMINATED_HTTPS']:
            new_transparent = listener['transparent']
            old_transparent = old_listener['transparent']
            if new_transparent != old_transparent:
                return True
        return False
