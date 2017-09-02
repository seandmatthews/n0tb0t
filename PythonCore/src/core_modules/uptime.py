import PythonCore.src.utils as utils


class UptimeMixin:
    def uptime(self, message):
        """
        Sends a message to stream saying how long the caster has been streaming for.

        !uptime
        """
        try:
            time_dict = self.service.get_live_time()
        except RuntimeError as e:
            time_dict = None
            utils.add_to_appropriate_chat_queue(self, message, str(e))
        if time_dict is not None:
            uptime_str = 'The channel has been live for {hours}, {minutes} and {seconds}.'.format(
                    hours=time_dict['hour'], minutes=time_dict['minute'], seconds=time_dict['second'])
            utils.add_to_public_chat_queue(self, uptime_str)
