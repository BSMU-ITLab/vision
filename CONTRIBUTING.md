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
	*Replace `new-branch-name` with your desired branch name.*
	*Use a descriptive branch name with some prefix:*
		- `feature/`: new features or enhancements.
		- `bugfix/`: bug fixes.
		- `hotfix/`: urgent fixes for critical issues.
		- `exp/`: experimental or exploratory work.
		- `docs/`: documentation updates.
		*Examples: `feature/add-brush-tool`, `bugfix/fix-mask-editing`, `hotfix/fix-critical-labeling-bug`, `exp/test-new-annotation-tool`, `docs/update-readme`.*

3. **Make your changes and add them to commit**:

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

4. **Commit your staged changes with a descriptive message:**

	```bash
	git commit -m "Describe your change here"
	```
	*Examples of commit message:*
		- `Add brush tool`
		- `Improve brush tool performance`
		- `Prevent data loss in annotation saving`

5. **Fetch and merge changes from the main branch (to ensure your branch is up to date with the latest changes)**:

	```bash
	git pull origin main
	```
	*If there are merge conflicts, resolve them as needed.*

6. **Push the current branch to the remote repository**:

	```bash
	git push origin HEAD
	```

7. **Create a Pull Request on GitHub**:

	- Go to the repository on GitHub.
	- Navigate to the ‘Pull requests’ tab and click on ‘New pull request’.
	- Choose `new-branch-name` as the branch you want to merge from.
	- Select the branch you want to merge into (usually the `main` branch of the repository).
	- Fill in the title and description for your pull request.
	- Click ‘Create pull request’.

8. **Review and merge the Pull Request**:

	- A collaborator will review your pull request.
	- Once approved, the pull request will be merged.
	- After merging, the remote branch will be deleted.

9. **Delete your local branch**:

	*After a branch has been merged and deleted on the remote repository, you can delete it locally.*
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
