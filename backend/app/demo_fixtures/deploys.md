# Deployments

## Strategy

We deploy using blue-green deployments. Traffic is shifted gradually from the blue
environment to the green environment over 10 minutes.

## Rollback

If error rates exceed 2% after a deploy, roll back with `make rollback`. A rollback
restores the previous blue environment within 30 seconds.

## Schedule

Production deploys happen on Tuesdays and Thursdays. There are no deploys on Fridays.
