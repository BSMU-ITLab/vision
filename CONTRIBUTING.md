# Instructions for Creating a Pull Request

1. **Ensure your repository is up to date**:

	*Fetch and integrate changes from the remote repository to your local repository:*
	```bash
	git pull origin main
	```

2. **Create and switch to a new branch**:

	```bash
	git switch -c new-branch-name
	```
	*Replace `new-branch-name` with your desired branch name.*<br>
	*Use a descriptive branch name with some prefix:*<br>
	- `feature/`: new features or enhancements.<br>
	- `bugfix/`: bug fixes.<br>
	- `hotfix/`: urgent fixes for critical issues.<br>
	- `exp/`: experimental or exploratory work.<br>
	- `docs/`: documentation updates.<br>
 
	*Examples of branch name with prefix:*<br>
	- `feature/add-brush-tool`<br>
	- `bugfix/fix-mask-editing`<br>
	- `hotfix/fix-critical-labeling-bug`<br>
	- `exp/test-new-annotation-tool`<br>
	- `docs/update-readme`<br>

4. **Make your changes and add them to commit**:

	```bash
	git status
	```
	*This command shows the status of your working directory and staging area. It helps you see which changes are staged for commit, which are not, and which files are untracked.*

	***Option 1: Stage specific files***

	```bash
	git add some-file
	```
	*Replace `some-file` with the name of the file you want to stage.*

	***Option 2: Stage all changes***

	```bash
	git add .
	```

5. **Commit your staged changes with a descriptive message:**

	```bash
	git commit -m "Describe your change here"
	```
	*Examples of commit message:*<br>
	- `Add brush tool`<br>
	- `Improve brush tool performance`<br>
	- `Prevent data loss in annotation saving`<br>

6. **Fetch and merge changes from the main branch (to ensure your branch is up to date with the latest changes)**:

	```bash
	git pull origin main
	```
	*If there are merge conflicts, resolve them as needed.*

7. **Push the current branch to the remote repository**:

	```bash
	git push origin HEAD
	```

8. **Create a Pull Request on GitHub**:

	- Go to the repository on GitHub.
	- Navigate to the `Pull requests` tab and click on `New pull request`.
	- Choose `new-branch-name` as the branch you want to merge from.
	- Select the branch you want to merge into (usually the `main` branch of the repository).
	- Fill in the title and description for your pull request.
	- Click `Create pull request`.

9. **Review and merge the Pull Request**:

	- A collaborator will review your pull request.
	- Once approved, the pull request will be merged.
	- After merging, the remote branch will be deleted.

10. **Delete your local branch**:

	*After a branch has been merged and deleted on the remote repository, you can delete it locally.*<br>
	*Switch to the main branch (you cannot delete the branch you are currently on):*
	```bash
	git switch main
	```

	*Update your local main branch with the latest changes from the remote repository (a branch that is not fully merged cannot be deleted):*
	```bash
	git pull
	```

	*Delete the local branch named `new-branch-name`:*
	
	```bash
	git branch -d new-branch-name
	```
