import java.util.*;

public class Problem19_SuffixAutomaton {
    // Suffix Automaton concept: O(n) construction, accepts all substrings
    static class State { int len, link; Map<Character, Integer> next = new HashMap<>(); State(int l, int li){len=l;link=li;} }
    List<State> states = new ArrayList<>();
    int last;

    public Problem19_SuffixAutomaton() { states.add(new State(0, -1)); last = 0; }

    public void extend(char c) {
        int cur = states.size();
        states.add(new State(states.get(last).len + 1, -1));
        int p = last;
        while (p != -1 && !states.get(p).next.containsKey(c)) { states.get(p).next.put(c, cur); p = states.get(p).link; }
        if (p == -1) states.get(cur).link = 0;
        else {
            int q = states.get(p).next.get(c);
            if (states.get(p).len + 1 == states.get(q).len) states.get(cur).link = q;
            else {
                int clone = states.size();
                State qState = states.get(q);
                states.add(new State(states.get(p).len + 1, qState.link));
                states.get(clone).next.putAll(qState.next);
                while (p != -1 && states.get(p).next.getOrDefault(c,-1) == q) { states.get(p).next.put(c, clone); p = states.get(p).link; }
                states.get(q).link = clone; states.get(cur).link = clone;
            }
        }
        last = cur;
    }

    public boolean contains(String pattern) {
        int cur = 0;
        for (char c : pattern.toCharArray()) { if (!states.get(cur).next.containsKey(c)) return false; cur = states.get(cur).next.get(c); }
        return true;
    }

    public static void main(String[] args) {
        Problem19_SuffixAutomaton sa = new Problem19_SuffixAutomaton();
        for (char c : "banana".toCharArray()) sa.extend(c);
        System.out.println(sa.contains("ana"));  // true
        System.out.println(sa.contains("xyz"));  // false
        System.out.println("States: " + sa.states.size());
    }
}
