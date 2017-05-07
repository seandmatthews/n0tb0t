import src.utils as utils


class UptimeMixin:
    def uptime(self):
        """
        Sends a message to stream saying how long the caster has been streaming for.

        !uptime
        """
        try:
            time_dict = utils.get_live_time()
        except RuntimeError as e:
            time_dict = None
            self._add_to_chat_queue(str(e))
        if time_dict is not None:
            uptime_str = 'The channel has been live for {hours}, {minutes} and {seconds}.'.format(
                    hours=time_dict['hour'], minutes=time_dict['minute'], seconds=time_dict['second'])
            self._add_to_chat_queue(uptime_str)
