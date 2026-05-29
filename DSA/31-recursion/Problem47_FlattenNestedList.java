import java.util.*;

public class Problem47_FlattenNestedList {
    interface NestedInteger { boolean isInteger(); Integer getInteger(); List<NestedInteger> getList(); }
    static class NI implements NestedInteger {
        Integer val; List<NestedInteger> list;
        NI(int v) { val = v; } NI(List<NestedInteger> l) { list = l; }
        public boolean isInteger() { return val != null; }
        public Integer getInteger() { return val; }
        public List<NestedInteger> getList() { return list; }
    }
    public static List<Integer> flatten(List<NestedInteger> nestedList) {
        List<Integer> res = new ArrayList<>();
        flattenHelper(nestedList, res);
        return res;
    }
    static void flattenHelper(List<NestedInteger> list, List<Integer> res) {
        for (NestedInteger ni : list) {
            if (ni.isInteger()) res.add(ni.getInteger());
            else flattenHelper(ni.getList(), res);
        }
    }
    public static void main(String[] args) {
        // [[1,1],2,[1,1]]
        List<NestedInteger> inner = Arrays.asList(new NI(1), new NI(1));
        List<NestedInteger> nested = Arrays.asList(new NI(inner), new NI(2), new NI(inner));
        System.out.println(flatten(nested)); // [1,1,2,1,1]
    }
}
