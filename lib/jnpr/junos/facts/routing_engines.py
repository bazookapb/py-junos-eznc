from string import maketrans
import re as RE

def routing_engines(junos, facts):

  tr = maketrans('-','_')

  re_facts = ['mastership-state','status','model','up-time','last-reboot-reason']
  re_info = junos.rpc.get_route_engine_information()

  master = []
  re_list = re_info.xpath('.//route-engine')
  if len(re_list) > 1: facts['2RE'] = True

  for re in re_list:
    x_re_name = re.xpath('ancestor::multi-routing-engine-item/re-name')

    if not x_re_name:
      # not a multi-instance routing engine platform, but could
      # have multiple RE slots
      re_name = "RE" 
      x_slot = re.find('slot')
      slot_id = x_slot.text if x_slot is not None else "0"
      re_name = re_name + slot_id
    else:
      # multi-instance routing platform
      m = RE.search('(\d)', x_re_name[0].text)
      re_name = "RE" + m.group(0)   # => RE0 | RE1

    re_fd = {}
    facts[re_name] = re_fd
    for factoid in re_facts:
      x_f = re.find(factoid)
      if x_f is not None:
        re_fd[factoid.translate(tr)] = x_f.text

    if 'mastership_state' in re_fd:
      if facts[re_name]['mastership_state'] == 'master':
        master.append(re_name)

  # --[ end for-each 're' ]----------------------------------------------------

  if facts['personality'].startswith('SRX'):
    # we should check the 'cluster status' on redundancy group 0 to see who is 
    # master.  we use a try/except block for cases when SRX is not clustered
    try:
      cluster_st = junos.rpc.get_chassis_cluster_status(redundancy_group="0")
      primary = cluster_st.xpath('.//redundancy-group-status[.="primary"]')[0]
      node = primary.xpath('preceding-sibling::device-name[1]')[0].text
      master.append(node.replace('node','RE'))
    except:
      # no cluster
      pass

  len_master = len(master)
  if len_master > 1:
    facts['master'] = master
  elif len_master == 1:
    facts['master'] = master[0]
