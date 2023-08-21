# Getting Started to Project

## Install Anaconda

Anaconda is a platform for Python that simplifies the process of development and deployment. It provides a package management system, called Conda, which allows you to easily install, update, and remove Python packages and dependencies. You can create an isolated development environment in a Terminal or when you create a new project in PyCharm.

- Download and Install Anaconda at [here](https://www.anaconda.com/)
- [Conda Cheat Sheet](https://docs.conda.io/projects/conda/en/4.6.0/_downloads/52a95608c49671267e40c689e0bc00ca/conda-cheatsheet.pdf)

## Install Node.js

Node.js is a JavaScript runtime environment that runs on the server-side, allowing developers to build powerful and scalable web applications using JavaScript outside of a web browser. 

- Download and Install Node.js LTS version at [here](https://nodejs.org/en)

## Install IDE

IDE stands for integrated development environment. In the pytc-client project, we will use [PyCharm Professional](https://www.jetbrains.com/lp/pycharm-pro/) as an IDE. You can get your educational license [here](https://www.jetbrains.com/community/education/#students).

## Source Management

Source management is the practice of tracking and managing changes to source code and other resources in software development project. The primary objectives of source management are:

1. Versioning: Allow to create and maintaining multiple versions, keep a history of changes over time
2. Collaboration: Provide a centralized repository where multiple developers can work on the same project simultaneously
3. Change tracking and accountability: Identify the origin of issues, track progress, and assign responsibility for specific changes
4. Backup and recovery: Act as a backup mechanism, safeguarding the project's source code and related assets

Source management tools (e.g.,  [Sourcetree](https://www.sourcetreeapp.com/), [Gitkraken](https://www.gitkraken.com/github-student-developer-pack-bundle)) help you get out of the command line interface and easily synchronize local files with remote repositories and visually check branch and commit history.

## Use Feature Branch Workflow

We will follow [feature branch workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/feature-branch-workflow). To begin working on a task, please assign your name to the task in the [Taskboard](https://www.notion.so/cb7e736315c94a5bb7a24680433d6d70?pvs=21).

- [Sync](https://www.atlassian.com/git/tutorials/syncing/git-pull) your local main branch with the remote main branch
- [Create a new branch](https://www.atlassian.com/git/tutorials/using-branches) using naming convention (e.g., jinhan/upload-files, jinhan/integrate-tensorboard)
- Commit your changes. [One commit, one change](https://fagnerbrack.com/one-commit-one-change-3d10b10cebbf).
- [Make a pull request](https://www.atlassian.com/git/tutorials/making-a-pull-request) when you are done your task
- Review the pull request by reviewers
- Merge into the main branch

## Create a New FastAPI Project

FastAPI app will be a server for the client. It handles Restful API requests via endpoints. 

In PyCharm,

- File > New Project
- Select FastAPI and Click Create
    - By default, a new Conda environment will be created.
    - In the left panel, click folder (Project) icon. You can browse files.

## Create React App

We will develop our user interface using React.js. [Create-react-app](https://create-react-app.dev/) generates a new React project with all the necessary files and dependencies preconfigured.

Install create-react-app

- `npm install -g create-react-app`

In PyCharm,

- Please click terminal icon in the bottom-left panel.
- `npx create-react-app {app-name}`

You will find {app-name} folder in the left project panel. 

## Run App

- To run FastAPI server, press ▶️ icon which located in top-right.
- To run React app, type `npm start` in terminal on the PyCharm.
- Open http://localhost:3000/ in your web browser

## Add Github account in Sourcetree

Create personal access token in Github

- Click your profile image on top right corner in github dashboard
- Click Settings
- Go to Developer settings > Personal access tokens > Tokens (classic)
- Select Generate new token (classic)
- Type name, choose expiration date (I choose no expiration date), and check repo
- Copy your token

Add Github account in Sourcetree

- Sourcetree > Settings > Accounts, click Add
    - Host: Github
    - Auth Type: Personal Access Token
    - Enter your Username
    - Paste your token
    - Protocol: HTTPS
    - Click Save

Clone repository in Sourcetree

- Click Remote tab, click clone
- Edit Destination path and click clone button

## Reading List

- [Clean Code](https://bc-primo.hosted.exlibrisgroup.com/primo-explore/fulldisplay?docid=ALMA-BC51558532920001021&context=L&tab=bcl_only&search_scope=bcl&vid=bclib_new&lang=en_US)
- [Refactoring](https://bc-primo.hosted.exlibrisgroup.com/primo-explore/fulldisplay?docid=ALMA-BC51536175150001021&context=L&vid=bclib_new&lang=en_US&search_scope=bcl&adaptor=Local%20Search%20Engine&tab=bcl_only&query=any,contains,Refactoring)
- [Test Driven Development with Python](https://bc-primo.hosted.exlibrisgroup.com/primo-explore/fulldisplay?docid=ALMA-BC51504659260001021&context=L&vid=bclib_new&lang=en_US&search_scope=bcl&adaptor=Local%20Search%20Engine&tab=bcl_only&query=any,contains,test%20driven%20development)
