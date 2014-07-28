# Copyright (c) 2003-2014 by Mike Jarvis
#
# TreeCorr is free software: redistribution and use in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions, and the disclaimer given in the accompanying LICENSE
#    file.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions, and the disclaimer given in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the {organization} nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.


def parse_variable(config, v):
    if '=' not in v:
        raise ValueError('Improper variable specification.  Use field.item=value.')
    key, value = v.split('=',1)
    key = key.strip()
    value = value.strip()
    # Cut off any trailing comment
    if '#' in value: value = value.split('#')[0]
    if value[0] == '{':
        values = value[1:-1].split(',')
    else:
        values = value.split() # on whitespace
        if len(values) == 1:
            config[key] = value
        else:
            config[key] = values

def parse_bool(value):
    if isinstance(value,str):
        if value.strip().upper() in [ 'TRUE', 'YES', 'T', 'Y' ]:
            return True
        elif value.strip().upper() in [ 'FALSE', 'NO', 'F', 'N', 'NONE' ]:
            return False
        else:
            try:
                val = bool(int(value))
                return val
            except:
                raise AttributeError("Unable to parse %s as a bool."%value)
    else:
        try:
            val = bool(value)
            return val
        except:
            raise AttributeError("Unable to parse %s as a bool."%value)


def read_config(file_name):
    """Read a configuration dict from a file.
    """
    config = dict()
    with open(file_name) as fin:
        for v in fin:
            v = v.strip()
            if len(v) == 0 or v[0] == '#':
                pass
            elif v[0] == '+':
                include_file_name = v[1:]
                read_config(include_file_name)
            else:
                parse_variable(config,v)
    return config

def setup_logger(verbose, log_file):
    """Parse the integer verbosity level from the command line args into a logging_level string
    """
    import logging
    logging_levels = {  0: logging.CRITICAL,
                        1: logging.WARNING,
                        2: logging.INFO,
                        3: logging.DEBUG }
    logging_level = logging_levels[verbose]

    # Setup logging to go to sys.stdout or (if requested) to an output file
    if log_file is None:
        import sys
        logging.basicConfig(format="%(message)s", level=logging_level, stream=sys.stdout)
    else:
        logging.basicConfig(format="%(message)s", level=logging_level, filename=log_file)
    return logging.getLogger('treecorr')

 
def check_config(config, params):
    """Check (and update) a config dict to conform to the given parameter rules.
    The params dict has an entry for each valid config parameter whose value is a tuple
    with the following items:
     - type
     - can be a list?
     - default value
     - valid values
     - description (Multiple entries here are allowed for longer strings)

    Returns the updated config dict.
    """
    for key in config:
        # Check that this is a valid key
        if key not in params:
            raise AttributeError("Invalid parameter %s found in config dict."%key)

        value_type, may_be_list, default_value, valid_values = params[key][:4]

        # Get the value
        if value_type is bool:
            value = parse_bool(config[key])
        else:
            value = value_type(config[key])

        # If limited allowed values, check that this is one of them.
        if valid_values is not None and value not in valid_values:
            raise AttributeError("Parameter %s has the invalid value %s.  Valid values are %s."%(
                key, config[key], str(valid_values)))

        # Write it back to the dict with the right type
        config[key] = value

    # Write the defaults for other parameters to simplify the syntax of getting the values
    for key in params:
        if key in config: continue
        value_type, may_be_list, default_value, valid_values = params[key][:4]
        config[key] = default_value

    return config

def print_params(params):
    """List the information about the valid parameters, given by the given params dict.
    See check_config for the structure of the params dict.
    """
    max_len = max(len(key) for key in params)
    for key in params:
        value_type, may_be_list, default_value, valid_values = params[key][:4]
        description = params[key][4:]
        print ("{0:<"+str(max_len)+"} {1}").format(key,description[0])
        for d in description[1:]:
            print "                {0}".format(d)

        # str(value_type) looks like "<type 'float'>"
        # value_type.__name__ looks like 'float'
        if may_be_list:
            print "                Type must be {0} or a list of {0}.".format(value_type.__name__)
        else:
            print "                Type must be {0}.".format(value_type.__name__)

        if valid_values is not None:
            print "                Valid values are {0!s}".format(valid_values)
        if default_value is not None:
            print "                Default value is {0!s}".format(default_value)
        print
