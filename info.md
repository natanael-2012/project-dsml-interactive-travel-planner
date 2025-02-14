Hello. Just a quick guide:

If you are Bashar or Karim, these are the folders that concern for the final version of the project:
- Useful notebooks are on the [notebooks](./notebooks/) folder. There is the cleaning of datasets, database creation, and the bot code (that still needs fixing)
- The [data](./data/) folder contains the datasets used in the notebooks in zip files. They were provided for this project
- The [flask](./flask/) folder contains the code for the web app. The main file is `app.py`, but most functions are located there too. They need to be reorganized to leave the main file cleaner

Less useful folders:
- The [docs to delete at the end](./docs%20to%20delete%20at%20the%20end/) folder contains the documentation that was used to create the project (such as drafts and other unusesd skeletons). It is not necessary for the final version. I did not delete them because they may serve for reference for other projects. 
- The [saves](./saves/) folder contain intermediate things that were saved during the project. They are not necessary for the final version, unless you want to build the database but not do all the preprocessing again. (use[all_docs_updated](./saves/all_docs_updated.pkl) for this. Its an array holding all the articles in `Document` objects)