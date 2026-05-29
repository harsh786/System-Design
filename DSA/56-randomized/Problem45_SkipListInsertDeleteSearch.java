import java.util.*;

public class Problem45_SkipListInsertDeleteSearch {
    static final int MAX_LEVEL = 16;
    static Random rand = new Random();
    static class Node { int val; Node[] next; Node(int v, int l) { val=v; next=new Node[l+1]; } }
    Node head = new Node(Integer.MIN_VALUE, MAX_LEVEL);
    int level = 0;

    int randLevel() { int l=0; while(rand.nextBoolean()&&l<MAX_LEVEL) l++; return l; }

    public void insert(int val) {
        Node[] update = new Node[MAX_LEVEL+1]; Node cur = head;
        for(int i=level;i>=0;i--){while(cur.next[i]!=null&&cur.next[i].val<val)cur=cur.next[i];update[i]=cur;}
        int nl=randLevel(); if(nl>level){for(int i=level+1;i<=nl;i++)update[i]=head;level=nl;}
        Node n=new Node(val,nl); for(int i=0;i<=nl;i++){n.next[i]=update[i].next[i];update[i].next[i]=n;}
    }

    public boolean search(int val) {
        Node cur=head; for(int i=level;i>=0;i--)while(cur.next[i]!=null&&cur.next[i].val<val)cur=cur.next[i];
        cur=cur.next[0]; return cur!=null&&cur.val==val;
    }

    public boolean delete(int val) {
        Node[] update=new Node[MAX_LEVEL+1]; Node cur=head;
        for(int i=level;i>=0;i--){while(cur.next[i]!=null&&cur.next[i].val<val)cur=cur.next[i];update[i]=cur;}
        cur=cur.next[0]; if(cur==null||cur.val!=val)return false;
        for(int i=0;i<=level;i++){if(update[i].next[i]!=cur)break;update[i].next[i]=cur.next[i];}
        while(level>0&&head.next[level]==null)level--;
        return true;
    }

    public static void main(String[] args) {
        Problem45_SkipListInsertDeleteSearch sl = new Problem45_SkipListInsertDeleteSearch();
        for(int v:new int[]{3,6,7,9,12,19,17,26})sl.insert(v);
        System.out.println(sl.search(19)); System.out.println(sl.delete(19)); System.out.println(sl.search(19));
    }
}
