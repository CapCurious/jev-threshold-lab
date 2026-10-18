# Record from the repository root: vhs docs/demo.tape
Output docs/demo.gif
Set Shell "bash"
Set FontSize 14
Set Width 960
Set Height 530
Set Padding 14
Set Theme "Dracula"
Set TypingSpeed 35ms
Set PlaybackSpeed 1

Hide
Type "export PS1='$ ' && clear"
Enter
Show

Type "python3 jev_threshold_lab.py --demo sweep --step 0.05"
Enter
Sleep 4s

Hide
Type "clear"
Enter
Show
Type "python3 jev_threshold_lab.py --demo bands --cost-fp 1 --cost-fn 10"
Enter
Sleep 3s

Hide
Type "clear"
Enter
Show
Type "python3 jev_threshold_lab.py --demo ladder"
Enter
Sleep 4s
