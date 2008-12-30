import Bcfg2.Server.Plugin, lxml.etree, re

probe_matcher = re.compile("(?P<basename>\S+)(.(?P<mode>[GH])_\S+)?")

class ProbeSet(Bcfg2.Server.Plugin.EntrySet):
    def __init__(self, path, fam, encoding, plugin_name):
        fpattern = '[0-9A-Za-z_\-]+'
        self.plugin_name = plugin_name
        Bcfg2.Server.Plugin.EntrySet.__init__(self, fpattern, path, True, 
                                              Bcfg2.Server.Plugin.SpecificData,
                                              encoding)
        fam.AddMonitor(path, self)
        self.bangline = re.compile('^#!(?P<interpreter>(/\w+)+)$')

    def HandleEvent(self, event):
        if event.filename != self.path:
            return self.handle_event(event)

    def get_probe_data(self, metadata):
        ret = []
        candidates = self.get_matching(metadata)
        temp = {}
        for cand in candidates:
            if cand.specific.all:
                if cand.name not in temp:
                    temp[cand.name] = (cand, 0)
                continue
            mdata = probe_matcher.match(cand.name).groupdict()
            if mdata['basename'] in temp:
                if mdata['mode'] > temp[mdata['basename']][1]:
                    temp[mdata['basename']] = (cand, mdata['mode'])
            else:
                temp[mdata['basename']] = (cand, mdata['mode'])
        
        for (name, data) in temp.iteritems():
            entry, prio = data
            probe = lxml.etree.Element('probe')
            probe.set('name', name.split('/')[-1])
            probe.set('source', self.plugin_name)
            probe.text = entry.data
            match = self.bangline.match(entry.data.split('\n')[0])
            if match:
                probe.set('interpreter', match.group('interpreter'))
            else:
                probe.set('interpreter', '/bin/sh')
            ret.append(probe)
        return ret

class Probes(Bcfg2.Server.Plugin.MetadataConnectorPlugin,
             Bcfg2.Server.Plugin.ProbingPlugin):
    __name__ = 'Probes'
    __version__ = '$Id: $'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.MetadataConnectorPlugin.__init__(self, core,
                                                             datastore)
        self.__name__ = 'Probes'
        try:
            self.probes = ProbeSet(self.data, core.fam, core.encoding,
                                   self.__name__)
        except:
            raise Bcfg2.Server.Plugin.PluginInitError

        self.probedata = dict()
        self.cgroups = dict()
        self.load_data()
    
    def write_data(self):
        '''write probe data out for use with bcfg2-info'''
        top = lxml.etree.Element("Probed")
        for client, probed in self.probedata.iteritems():
            cx = lxml.etree.SubElement(top, 'Client', name=client)
            for probe in probed:
                lxml.etree.SubElement(cx, 'Probe', name=probe,
                                      value=self.probedata[client][probe])
            for group in self.cgroups[client]:
                lxml.etree.SubElement(cx, "Group", name=group)
        data = lxml.etree.tostring(top, encoding='UTF-8', xml_declaration=True,
                                   pretty_print='true')
        try:
            datafile = open("%s/%s" % (self.data, 'probed.xml'), 'w')
        except IOError:
            self.logger.error("Failed to write probed.xml")
        datafile.write(data)

    def load_data(self):
        try:
            data = lxml.etree.parse(self.data + '/probed.xml').getroot()
        except:
            self.logger.error("Failed to read file probed.xml")
            return
        self.probedata = {}
        self.cgroups = {}
        for client in data.getchildren():
            self.probedata[client.get('name')] = {}
            self.cgroups[client.get('name')]=[]
            for pdata in client:
                if (pdata.tag == 'Probe'):
                    self.probedata[client.get('name')][pdata.get('name')] = pdata.get('value')
                elif (pdata.tag == 'Group'):
                    self.cgroups[client.get('name')].append(pdata.get('name'))

    def GetProbes(self, meta, force=False):
        '''Return a set of probes for execution on client'''
        return self.probes.get_probe_data(meta)

    def ReceiveData(self, client, datalist):
        self.cgroups[client.hostname] = []
        self.probedata[client.hostname] = {}
        for data in datalist:
            self.ReceiveDataItem(client, data)
        self.write_data()

    def ReceiveDataItem(self, client, data):
        '''Receive probe results pertaining to client'''
        if not self.cgroups.has_key(client.hostname):
            self.cgroups[client.hostname] = []
        if data.text == None:
            self.logger.error("Got null response to probe %s from %s" % \
                              (data.get('name'), client.hostname))
            try:
                self.probedata[client.hostname].update({data.get('name'): ''})
            except KeyError:
                self.probedata[client.hostname] = {data.get('name'): ''}
            return
        dlines = data.text.split('\n')
        self.logger.debug("%s:probe:%s:%s" % (client.hostname, 
            data.get('name'), [line.strip() for line in dlines]))
        for line in dlines[:]:
            if line.split(':')[0] == 'group':
                newgroup = line.split(':')[1].strip()
                if newgroup not in self.cgroups[client.hostname]:
                    self.cgroups[client.hostname].append(newgroup)
                dlines.remove(line)
        dtext = "\n".join(dlines)
        try:
            self.probedata[client.hostname].update({ data.get('name'):dtext })
        except KeyError:
            self.probedata[client.hostname] = { data.get('name'):dtext }

    def get_additional_metadata(self, meta):
        return (self.cgroups.get(meta.hostname, list()),
                self.probedata.get(meta.hostname, dict()))