""" This function specifically parses the "SimTime" field as a special field
in predicate parsing. """


def left_side_value(data, field):
    """Left side value grabs the correct field value"""
    if field == "SimTime":
        return data[0]
    else:
        return data[1][field]
