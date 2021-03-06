*This repo is https://git.dn42.dev/dn42/registry  
If you are using a different url, please update as soon as possible*

# Guide for creating a Pull Request

1. **Create a local clone of the registry repository**

```sh
git clone git@git.dn42.dev:dn42/registry.git
```

*You do not need to fork the registry repository. New users are provisioned as collaborators, allowing everyone permission to create new branches in the main registry repository. Note that this process is triggered on first login as a new user and can take up to 10 minutes. If you get permission denied trying to create a branch then log out and back in to your gitea account then retry after a few minutes.*

2. **Create a branch for your changes**

The name of the branch ***must*** follow a specific format:
`<username>-YYYYMMDD/<name>`  
 - `<username>` is your gitea username.  
 - `YYYYMMDD` is the current date.  
 - `<name>` is a descriptive name for your change.

The branch must be created in the registry on the date described in the branch name, so create the branch and push it to the registry immediately.

```sh
# create a new branch and switch to it

git checkout -b foo-20200704/mychange

# push it immediately to the registry

git push --set-upstream origin foo-20200704/mychange
```

3. **Make your changes on your new branch**

See the [getting started](https://dn42.dev/howto/Getting-Started) guide in the [Wiki](https://dn42.dev) for more information.

- `inet6num` must have a random prefix to satisfy [RFC4193](https://tools.ietf.org/html/rfc4193)
- Include an [auth method](https://dn42.dev/howto/Registry-Authentication) in your MNTNER so you changes to your objects can be authenticated
- Run the schema checking tools to validate your changes
  - `./fmt-my-stuff MNTNER-MNT`
  - `./check-my-stuff MNTNER-MNT`
  - `./check-pol origin/master MNTNER-MNT`

```sh
$EDITOR mychanges
git add .
git commit
```

4. **Push your changes back to the registry**

You must squash multiple commits together and sign them using your MNTNER [authentication method](https://dn42.dev/howto/Registry-Authentication).  
It is also good practice to rebase your work on top of any other changes that may have happened on the master branch.

The registry contains a script that will automatically rebase and squash your commits:

```sh
./squash-my-commits
git push --force
```

or you can do it manually:

```sh
# make sure your local copy of the master is up to date

git fetch origin master

# ensure you are using your new branch

git checkout foo-20200704/mychange 

# rebase your branch on top of the master
#
# -i to interactively pick the commits
# -S to sign the result with your GPG key (not required for SSH authentication)
#
# In interactive mode, make sure the first commit says 'pick'
# change the rest from 'pick' to 'squash'
# save and close to create the commit

git rebase -i -S origin/master

# force push your changes back to the registry

git push --force
```

5. **Create a pull request**

In the gitea GUI, select your branch, check your changes again for a final time and then hit the 'Pull Request' button.

If you are using SSH authentication, please post the full commit hash that you signed and SSH signature in to the PR comments.

Your changes will now go through automatic checking and then manual review by the registry maintainers. 

6. **Making updates**

If you need to make changes to fix review issues simply make the updates to your branch and follow the process in (4) to rebase, squash and sign your changes again. **You must do this for every update**.

Do not close and re-open a new pull request, any changes you make on your branch will be automatically updated in the PR. Creating a new PR loses all the history and makes tracking changes harder.

# Gitea Usage

The DN42 registry is a community resource for *your* benefit.
Registered users are free to create and use their own repositories and use the Drone CI tools, but please be considerate in your usage.

 - Repositories should be related to DN42
 - Do not create tools that make regular, automated, push changes to repositories unless agreed with the registry maintainers
 - Do not just create a mirror of other, publically available, repositories

# Data Privacy

Gitea and the DN42 registry contains personal information for users who are registered in DN42; this information is stored in Canada and viewable by any registered member. In addition, anyone with access to the repository is able to make their own copies of the registry, which they may then process or transfer in arbitrary ways. You must assume that all data entered in to the registry cannot be kept private and will be made publically available. 

Any personal information stored in the registry is optional and voluntarily provided by you. Whilst the registry maintainers will make best efforts to update or delete personal data, you must accept that the technical restrictions of git may make this impossible and that your information will likely have been distributed beyond the control of the registry maintainers.  

If this is not acceptable for you, you must not upload your personal details to the registry.

All registered users have the capability to make copies of the registry data for their own use. If you do copy the registry you must ensure that any copies you make are deleted when no longer required and that you will make best efforts to update or delete personal data when requested.
