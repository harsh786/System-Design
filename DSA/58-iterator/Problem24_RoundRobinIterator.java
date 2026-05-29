import java.util.*;

public class Problem24_RoundRobinIterator implements Iterator<Integer> {
    List<Iterator<Integer>> iterators;
    Queue<Integer> queue = new LinkedList<>();

    public Problem24_RoundRobinIterator(List<List<Integer>> lists) {
        iterators = new ArrayList<>();
        for (int i = 0; i < lists.size(); i++) if (!lists.get(i).isEmpty()) {
            iterators.add(lists.get(i).iterator());
            queue.offer(iterators.size()-1);
        }
    }

    public boolean hasNext() { return !queue.isEmpty(); }

    public Integer next() {
        int idx = queue.poll();
        int val = iterators.get(idx).next();
        if (iterators.get(idx).hasNext()) queue.offer(idx);
        return val;
    }

    public static void main(String[] args) {
        List<List<Integer>> lists = Arrays.asList(Arrays.asList(1,4,7), Arrays.asList(2,5), Arrays.asList(3,6,8,9));
        Problem24_RoundRobinIterator it = new Problem24_RoundRobinIterator(lists);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 1 2 3 4 5 6 7 8 9
    }
}
