public class Problem03_MergeTwoSortedLists {
    static class ListNode{int val;ListNode next;ListNode(int v){val=v;}}
    
    static ListNode mergeTwoLists(ListNode l1,ListNode l2){
        ListNode d=new ListNode(0),c=d;
        while(l1!=null&&l2!=null){if(l1.val<=l2.val){c.next=l1;l1=l1.next;}else{c.next=l2;l2=l2.next;}c=c.next;}
        c.next=l1!=null?l1:l2;return d.next;
    }
    
    public static void main(String[] args) {
        ListNode a=new ListNode(1);a.next=new ListNode(3);a.next.next=new ListNode(5);
        ListNode b=new ListNode(2);b.next=new ListNode(4);b.next.next=new ListNode(6);
        ListNode r=mergeTwoLists(a,b);while(r!=null){System.out.print(r.val+" ");r=r.next;}System.out.println();
    }
}
