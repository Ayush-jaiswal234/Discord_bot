import requests

def logging_in_to_pnw():
	try:
		session=requests.session()
		login_url='https://test.politicsandwar.com/login/'
		login_data={'password':'3duq3NjyLQ7B@ir','email':'jaiswalayush833@gmail.com','loginform':'login'}
		login=session.post(f"{login_url}",login_data)
		print('logged in successfully')
		return session
	except:
		print('an error occured')	
pass