# stdlib
from inspect import isclass
from time import time
from datetime import datetime
import os

# 3rd-party
from lxml import etree

_TSFMT = "%Y%m%d%H%M%S"

class Table(object):
  ITEM_XPATH = None
  ITEM_NAME_XPATH = 'name'
  VIEW = None

  def __init__(self, dev=None, xml=None, path=None):
    """
    :dev: Device instance
    :xml: lxml Element instance 
    :path: file path to XML, to be used rather than :dev:
    """
    self._dev = dev 
    self.xml = xml
    self.view = self.VIEW
    self._key_list = []
    self._path = path

  ##### -------------------------------------------------------------------------
  ##### PROPERTIES
  ##### -------------------------------------------------------------------------    

  @property 
  def D(self):
    """ the Device instance """
    return self._dev

  @property 
  def RPC(self):
    """ the Device.rpc instance """
    return self.D.rpc

  @property
  def view(self):
    """ returns the current view assigned to this table """
    return self._view

  @view.setter
  def view(self, cls):
    """ assigns a new view to the table """
    if cls is None:
      self._view = None
      return

    if not isclass(cls):
      raise ValueError("Must be given RunstatView class")

    self._view = cls

  @property
  def hostname(self):
    return self.D.hostname

  @property 
  def is_container(self):
    """ 
    True if this table does not have records, but is a container of fields
    False otherwise
    """
    return self.ITEM_XPATH is None    

  @property
  def key_list(self):
    """ the list of keys, as property for caching """
    return self._key_list
  
  ##### -------------------------------------------------------------------------
  ##### PRIVATE METHODS
  ##### -------------------------------------------------------------------------  

  def _assert_data(self):
    if self.xml is None: raise RuntimeError("Table is empty, use get()")    

  def _keys_composite(self, xpath, key_list):
    """ composite keys return a tuple of key-items """
#    _tkey = lambda this: tuple([this.findtext(k) for k in key_list ])
    _tkey = lambda this: tuple([this.xpath(k)[0].text for k in key_list ])
    return [_tkey(item) for item in self.xml.xpath(xpath)]

  def _keys_simple(self, xpath):
    return [x.text.strip() for x in self.xml.xpath(xpath)]

  def _keyspec(self):
    """ returns tuple (keyname-xpath, item-xpath) """    
    return (self.ITEM_NAME_XPATH, self.ITEM_XPATH)

  ##### -------------------------------------------------------------------------
  ##### PUBLIC METHODS
  ##### -------------------------------------------------------------------------    


  ## --------------------------------------------------------------------------
  ## keys
  ## --------------------------------------------------------------------------

  def _keys(self):
    """ return a list of data item keys from the Table XML """

    self._assert_data()
    key_value, xpath = self._keyspec()

    if isinstance(key_value, str):
      return self._keys_simple( xpath+'/'+key_value)

    if not isinstance( key_value, list ): 
      raise RuntimeError("What to do with key, table:'%'" % self.__class__.__name__)

    # ok, so it's a list, which means we need to extract tuple values
    return self._keys_composite( xpath, key_value )

  def keys(self):
    # if the key_list has been cached, then use it
    if len(self.key_list): return self.key_list

    # otherwise, build the list of keys into the cache
    self._key_list = self._keys()
    return self._key_list

  ## --------------------------------------------------------------------------
  ## values
  ## --------------------------------------------------------------------------

  def values(self):
    """ returns list of table entry items() """

    self._assert_data()
    if self.view is None:
      # no View, so provide XML for each item
      return [this for this in self]
    else:
      # view object for each item
      return [this.items() for this in self]

  ## --------------------------------------------------------------------------
  ## items
  ## --------------------------------------------------------------------------

  def items(self):
    """ returns list of tuple(name,values) for each table entry """
    return zip(self.keys(), self.values())

  ## --------------------------------------------------------------------------
  ## get - loads the data from source
  ## --------------------------------------------------------------------------

  def get(self, *vargs, **kvargs):
    # implemented by either OpTable or CfgTable
    # @@@ perhaps this should raise an exception rather than just 'pass', ??
    pass

  ## --------------------------------------------------------------------------
  ## savexml - saves the table XML to a local file
  ## --------------------------------------------------------------------------

  def savexml(self, path, hostname=False, timestamp=False ):
    fname, fext = os.path.splitext(path)

    if hostname is True:
      fname += "_%s" % self.D.hostname

    if timestamp is True:
      tsfmt = datetime.fromtimestamp(time()).strftime(_TSFMT)
      fname += "_%s" % tsfmt

    path = fname + fext
    return etree.ElementTree(self.xml).write(file(path,'w'))

  ##### -------------------------------------------------------------------------
  ##### OVERLOADS
  ##### -------------------------------------------------------------------------    

  __call__ = get

  def __repr__(self):
    cls_name = self.__class__.__name__
    source = self.D.hostname if self.D is not None else self._path

    if self.xml is None:
      return "%s:%s - Table empty" % (cls_name, source)
    else:
      n_items = len(self.keys())
      return "%s:%s: %s items" % (cls_name, source, n_items)

  def __len__(self):
    self._assert_data()    
    return len(self.keys())

  def __iter__(self):
    """ iterate over each time in the table """
    self._assert_data()

    as_xml = lambda table,view_xml: view_xml
    view_as = self.view or as_xml

    for this in self.xml.xpath(self.ITEM_XPATH):
      yield view_as( self, this )    

  def __getitem__(self, value):
    """
    returns a table item.  if a table view is set (should be by default) then
    the item will be converted to the view upon return.  if there is no table 
    view, then the XML object will be returned.

    :value:
      when it is a <string>, this will perform a select based on the key-name
      when it is a <tuple>, this will perform a select based on the compsite key-name
      when it is an <int>, this will perform a select based by position, like <list>
        [0] is the first item 
        [-1] is the last item
      when it is a <slice> then this will return a <list> of View widgets
    """
    self._assert_data()

    if isinstance(value,int):
      # if selection by index, then grab the key at this index and
      # recursively call this method using that key, yo!
      return self.__getitem__(self.key_list[value])

    if isinstance(value,slice):
      # implements the 'slice' mechanism
      return [self.__getitem__(key) for key in self.key_list[value]]

    # ---[ get_xpath ] --------------------------------------------------------

    def get_xpath(find_value):
      namekey_xpath, item_xpath = self._keyspec()      
      xnkv = '[normalize-space({})="{}"]'

      if isinstance(find_value,str):
        # find by name, simple key
        return item_xpath + xnkv.format( namekey_xpath, find_value)

      if isinstance(find_value,tuple):
        # composite key (value1, value2, ...) will create an
        # iterative xpath of the fmt statement for each key/value pair
        xpf = ''.join([xnkv.format(k.replace('_','-'),v) for k,v in zip(namekey_xpath, find_value)])
        return item_xpath + xpf    

    # ---[END: get_xpath ] --------------------------------------------------------

    found = self.xml.xpath(get_xpath( value ))
    if not len(found): return None

    as_xml = lambda table,view_xml: view_xml
    use_view = self.view or as_xml

    return use_view( table=self, view_xml=found[0] ) 

  def __contains__(self,key):
    """ membership for use with 'in' """
    return bool(key in self.key_list)