class Message:
	'''
	So what does a message have?
	a service (twitch, beam, whatever)
	a message type (whisper, public message, direct message, etc?)
	a user (who sent the message)
	message content = "!ogod buzzer baby"

	The goal is for the bot to act_on(Message)
	And for the but to push down sockets varous Messages
	This should just hold data...
	'''
	service = DEFAULT_SERVICE
	message_type = DEFAULT_MESSAGE_TYPE
	user = DEFAULT_USER
	content = DEFAULT_CONTENT