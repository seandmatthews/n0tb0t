import json


class ConfigManager:
    def __init__():
        pass#@todo(aaron): decide if anything needs to happen here


    def save_service_config(service_config):
        '''
        preconditions:
            1. service_config is a dict
            2. service_config['save_location'] is a valid filepath
            3. the n0tb0t config does not have another service with the same nickname

        postconditions:
            1. If all preconditions are met then it will save the dict at service_config['save_location']/config.json
            2. If precondition 1 is not met then a TypeError will be raised.
            3. If precondition 2 is not met then a FileNotFoundError will be raised.
            4. If precondition 3 is not met then a FileExistsError will be raised.
        '''
        if not isinstance(service_config, dict):
            raise TypeError("save_service_config should take a dict, you gave it {}.".format(type(service_config)))
        #@todo(aaron): implement the rest of this


    def load_service_config(file_path):
        '''
        preconditions:
            1. file path is a valid filepath
                * it should be accessible from the location where n0tb0t is run (e.g. ~/n0tb0t/$SOMEWHERE)
            2. there is a json file at the filepath containing valid service config

        postconditions:
            1. If all the preconditions are met then it will load a service config dict from json and create the service object
            2. If precondition 1 is not met then a FileNotFoundError will be raised
            3. If precondition 2 is not met then a TypeError will be raised
        '''
        pass


    def save_command_config(command_config):
        '''
        preconditions:
            1. commnad_config is a dict
            2. command_config['save_location'] is a valid filepath
            3. the service config does not have another command with the same nickname

        postconditions:
            1. If all preconditions are met then it will save the dict at command_config['save_location']/config.json
            2. If precondition 1 is not met then a TypeError will be raised.
            3. If precondition 2 is not met then a FileNotFoundError will be raised.
            4. If precondition 3 is not met then a FileExistsError will be raised.
        '''
        pass


    def load_command_config(file_path):
        '''
        preconditions:
            1. file path is a valid filepath
                * it should be accessible from the location where n0tb0t is run (e.g. ~/n0tb0t/$SOMEWHERE)
            2. there is a json file at the filepath containing valid command config

        postconditions:
            1. If all the preconditions are met then it will load a command config dict from json and create the command object
            2. If precondition 1 is not met then a FileNotFoundError will be raised
            3. If precondition 2 is not met then a TypeError will be raised
        '''
        pass
