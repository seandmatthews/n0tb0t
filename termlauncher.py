'''
this file will obsolete run.py
'''
import src.config_manager
import src.bot

if __name__ == "__main__":
    main()

def config():
    pass


def run():
    '''
    @todo(aaron): code this

    this will create a servicemanager class or somethit in the bot.py file
    then pass it a list of file locations for the services' config
        THAT CLASS WILL make the services
        then give the services a string containing the directory where their command module configs should be
            and the service will go to that directory and open all the json files
            THEN MAKE COMMAND OBJECTS FROM THE json

    its json ALL THE WAY DOWN YAAAA
    '''
    pass


def main():
    print("Starting n0tb0t.")
    keep_running = True
    while keep_running:
        print("Welcome to the terminal version of n0tb0t. Please select an option:")
        print("    1. Service configuration editor")
        print("    2. Launch the bot")
        choice = input("Enter your selection here:")
        if choice == "1":
            config()
        elif choice == "2":
            run()
