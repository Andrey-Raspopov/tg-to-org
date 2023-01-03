import { Selector } from 'testcafe';

fixture('Getting Started')
    .page('http://127.0.0.1:5000');

test('My first test', async t => {
    await t
        .click('#channels')
        .expect(Selector('#channels-container').innerText).contains('Гретцки Орех');
});