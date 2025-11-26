from granian import Granian
from config import rsgi_app
from granian import loops
from uvicorn import run

if __name__ == "__main__":
    run(app="config:app", host="localhost", port=8000,reload=True)
    # runner = Granian( "config:rsgi_app", "127.0.0.1", 8000, reload=True, log_level="error", interface="rsgi")
    # runner.serve()



# @cli.command()
# def runserver(): 
#     runner = Granian( "config:app", "0.0.0.0", "8000", reload=True, log_level="error", interface="asgi" ) 
#     runner.serve()