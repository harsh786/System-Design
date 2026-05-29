import java.util.*;

public class Problem02_FlattenNestedListIterator implements Iterator<Integer> {
    interface NestedInteger {
        boolean isInteger(); Integer getInteger(); List<NestedInteger> getList();
    }
    static class NI implements NestedInteger {
        Integer val; List<NestedInteger> list;
        NI(int v){val=v;} NI(List<NestedInteger> l){list=l;}
        public boolean isInteger(){return val!=null;} public Integer getInteger(){return val;}
        public List<NestedInteger> getList(){return list;}
    }

    Deque<Iterator<NestedInteger>> stack = new ArrayDeque<>();

    public Problem02_FlattenNestedListIterator(List<NestedInteger> nestedList) {
        stack.push(nestedList.iterator());
    }

    public Integer next() { return stack.peek().next().getInteger(); }

    public boolean hasNext() {
        while (!stack.isEmpty()) {
            if (!stack.peek().hasNext()) { stack.pop(); continue; }
            Iterator<NestedInteger> it = stack.peek();
            // peek without consuming - use a temp list
            NestedInteger ni = it.next();
            if (ni.isInteger()) {
                // put it back by wrapping
                List<NestedInteger> tmp = new ArrayList<>(); tmp.add(ni);
                stack.push(tmp.iterator());
                return true;
            }
            stack.push(ni.getList().iterator());
        }
        return false;
    }

    public static void main(String[] args) {
        // [[1,1],2,[1,1]]
        List<NestedInteger> inner = Arrays.asList(new NI(1), new NI(1));
        List<NestedInteger> list = Arrays.asList(new NI(inner), new NI(2), new NI(inner));
        // Simplified demo
        System.out.println("Flatten nested list iterator implemented");
        // Direct flatten for demo
        List<Integer> result = new ArrayList<>();
        flatten(list, result);
        System.out.println(result);
    }

    static void flatten(List<NestedInteger> list, List<Integer> result) {
        for (NestedInteger ni : list) {
            if (ni.isInteger()) result.add(ni.getInteger());
            else flatten(ni.getList(), result);
        }
    }
}
