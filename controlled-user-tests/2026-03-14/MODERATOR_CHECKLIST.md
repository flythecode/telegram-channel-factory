# Moderator checklist — first controlled user test wave

## Before participant joins
- [ ] Test bot replies to `/start`
- [ ] Environment is safe (`APP_ENV=staging`, `RUNTIME_MODE=demo`, `PUBLISHER_BACKEND=stub`)
- [ ] `FIRST_USER_LAUNCH_PATH.md` is ready to send to participant
- [ ] Open the matching participant file (`PARTICIPANT_01.md` / `02` / `03`)
- [ ] Fill header fields: date, participant, profile, moderator, environment
- [ ] Reminder to moderator: do not explain the UI before the participant gets stuck

## During test
- [ ] Ask participant to think aloud
- [ ] Run Scenario A without hints unless participant is blocked
- [ ] Run Scenario B without hints unless participant is blocked
- [ ] Run Scenario C without hints unless participant is blocked
- [ ] Record every hesitation >10 seconds
- [ ] Record every direct request for help
- [ ] Record exact confusing labels / missing next step

## After each participant
- [ ] Fill summary: blockers, delights, severity, recommended follow-up backlog item
- [ ] Save file in this folder
- [ ] Confirm whether participant reached first publication

## Done criteria for backlog item 63
- [ ] At least 2 real participants completed the test on the Telegram test bot
- [ ] Separate filled result file exists for each participant
- [ ] Report contains real UX pains and strengths
- [ ] Next backlog item 64 is based on observed feedback, not assumptions
